// WebGL 2 renderer for the brain graph: edges as lines, nodes as instanced quads.
import type { Camera } from "./model";

export type Rgba = [number, number, number, number];

const NODE_VS = `#version 300 es
in vec2 corner;
in vec2 center;
in float radius;
in vec4 color;
uniform vec3 cam;
uniform vec2 viewport;
uniform float dpr;
out vec2 v_corner;
out vec4 v_color;
void main() {
  vec2 px = center * cam.x + cam.yz + corner * radius * dpr;
  vec2 clip = px / viewport * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
  v_corner = corner;
  v_color = color;
}`;

const NODE_FS = `#version 300 es
precision mediump float;
in vec2 v_corner;
in vec4 v_color;
out vec4 frag;
void main() {
  float d = length(v_corner);
  if (d > 1.0) discard;
  frag = vec4(v_color.rgb, v_color.a * smoothstep(1.0, 0.8, d));
}`;

const EDGE_VS = `#version 300 es
in vec2 pos;
uniform vec3 cam;
uniform vec2 viewport;
void main() {
  vec2 px = pos * cam.x + cam.yz;
  vec2 clip = px / viewport * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
}`;

const EDGE_FS = `#version 300 es
precision mediump float;
uniform vec4 edgeColor;
out vec4 frag;
void main() {
  frag = edgeColor;
}`;

function compile(
  gl: WebGL2RenderingContext,
  type: number,
  src: string,
): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL could not create a shader");
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(`Shader failed to compile: ${gl.getShaderInfoLog(shader)}`);
  }
  return shader;
}

function program(
  gl: WebGL2RenderingContext,
  vs: string,
  fs: string,
): WebGLProgram {
  const prog = gl.createProgram();
  if (!prog) throw new Error("WebGL could not create a program");
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, vs));
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    throw new Error(`Program failed to link: ${gl.getProgramInfoLog(prog)}`);
  }
  return prog;
}

function buffer(
  gl: WebGL2RenderingContext,
  target: number,
  data: ArrayBufferView,
): WebGLBuffer {
  const buf = gl.createBuffer();
  if (!buf) throw new Error("WebGL could not create a buffer");
  gl.bindBuffer(target, buf);
  gl.bufferData(target, data, gl.DYNAMIC_DRAW);
  return buf;
}

export class BrainRenderer {
  private readonly gl: WebGL2RenderingContext;
  private readonly nodeProg: WebGLProgram;
  private readonly edgeProg: WebGLProgram;
  private readonly nodeVao: WebGLVertexArrayObject;
  private readonly edgeVao: WebGLVertexArrayObject;
  private readonly centerBuf: WebGLBuffer;
  private readonly radiusBuf: WebGLBuffer;
  private readonly colorBuf: WebGLBuffer;
  private readonly edgeBuf: WebGLBuffer;
  private dpr = 1;
  private nodeCount = 0;
  private edgeVertexCount = 0;
  private edges: Uint32Array = new Uint32Array(0);
  private lines: Float32Array = new Float32Array(0);

  constructor(private readonly canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", {
      alpha: false,
      antialias: true,
      powerPreference: "low-power",
    });
    if (!gl) throw new Error("WebGL 2 is not available in this window");
    this.gl = gl;
    this.nodeProg = program(gl, NODE_VS, NODE_FS);
    this.edgeProg = program(gl, EDGE_VS, EDGE_FS);

    const quad = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
    this.centerBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.radiusBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.colorBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.edgeBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));

    this.nodeVao = this.makeVao(() => {
      const corner = buffer(gl, gl.ARRAY_BUFFER, quad);
      this.bindAttr(this.nodeProg, "corner", corner, 2, 0);
      this.bindAttr(this.nodeProg, "center", this.centerBuf, 2, 1);
      this.bindAttr(this.nodeProg, "radius", this.radiusBuf, 1, 1);
      this.bindAttr(this.nodeProg, "color", this.colorBuf, 4, 1);
    });
    this.edgeVao = this.makeVao(() => {
      this.bindAttr(this.edgeProg, "pos", this.edgeBuf, 2, 0);
    });
  }

  private makeVao(setup: () => void): WebGLVertexArrayObject {
    const vao = this.gl.createVertexArray();
    if (!vao) throw new Error("WebGL could not create a vertex array");
    this.gl.bindVertexArray(vao);
    setup();
    this.gl.bindVertexArray(null);
    return vao;
  }

  private bindAttr(
    prog: WebGLProgram,
    name: string,
    buf: WebGLBuffer,
    size: number,
    divisor: number,
  ): void {
    const gl = this.gl;
    const loc = gl.getAttribLocation(prog, name);
    if (loc < 0) return;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    gl.vertexAttribDivisor(loc, divisor);
  }

  /** `pos` is interleaved x, y per node; `edges` is interleaved node index pairs. */
  setGraph(pos: Float32Array, edges: Uint32Array): void {
    const gl = this.gl;
    this.edges = edges;
    this.lines = new Float32Array(edges.length * 2);
    this.nodeCount = pos.length / 2;
    this.edgeVertexCount = this.lines.length / 2;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.centerBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.edgeBuf);
    gl.bufferData(gl.ARRAY_BUFFER, this.lines, gl.DYNAMIC_DRAW);
    this.setPositions(pos);
  }

  /** Move the nodes (and the edges between them) to new positions, same count as setGraph. */
  setPositions(pos: Float32Array): void {
    const gl = this.gl;
    const lines = this.lines;
    for (let i = 0; i < this.edges.length; i++) {
      const n = this.edges[i] ?? 0;
      lines[2 * i] = pos[2 * n] ?? 0;
      lines[2 * i + 1] = pos[2 * n + 1] ?? 0;
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, this.centerBuf);
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, pos);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.edgeBuf);
    gl.bufferSubData(gl.ARRAY_BUFFER, 0, lines);
  }

  /** One radius (px) per node. */
  setRadii(radii: Float32Array): void {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.radiusBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, radii, this.gl.DYNAMIC_DRAW);
  }

  /** One RGBA colour (0 to 1) per node, four floats each. */
  setColors(colors: Float32Array): void {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.colorBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, colors, this.gl.DYNAMIC_DRAW);
  }

  /** Match the canvas backing store to its CSS size, with the device pixel ratio capped. */
  resize(cssWidth: number, cssHeight: number, dprCap: number): void {
    this.dpr = Math.min(window.devicePixelRatio || 1, dprCap);
    this.canvas.width = Math.max(1, Math.round(cssWidth * this.dpr));
    this.canvas.height = Math.max(1, Math.round(cssHeight * this.dpr));
    this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
  }

  draw(cam: Camera, background: Rgba, edgeColor: Rgba): void {
    const gl = this.gl;
    const cvp: [number, number] = [this.canvas.width, this.canvas.height];
    // Camera values are in CSS pixels; scale them to the backing store.
    const dpr = this.dpr;
    const camU: [number, number, number] = [
      cam.zoom * dpr,
      cam.x * dpr,
      cam.y * dpr,
    ];
    gl.clearColor(...background);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    gl.useProgram(this.edgeProg);
    gl.uniform3f(gl.getUniformLocation(this.edgeProg, "cam"), ...camU);
    gl.uniform2f(gl.getUniformLocation(this.edgeProg, "viewport"), ...cvp);
    gl.uniform4f(
      gl.getUniformLocation(this.edgeProg, "edgeColor"),
      ...edgeColor,
    );
    gl.bindVertexArray(this.edgeVao);
    gl.drawArrays(gl.LINES, 0, this.edgeVertexCount);

    gl.useProgram(this.nodeProg);
    gl.uniform3f(gl.getUniformLocation(this.nodeProg, "cam"), ...camU);
    gl.uniform2f(gl.getUniformLocation(this.nodeProg, "viewport"), ...cvp);
    gl.uniform1f(gl.getUniformLocation(this.nodeProg, "dpr"), dpr);
    gl.bindVertexArray(this.nodeVao);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.nodeCount);
    gl.bindVertexArray(null);
  }

  dispose(): void {
    const gl = this.gl;
    gl.deleteProgram(this.nodeProg);
    gl.deleteProgram(this.edgeProg);
    for (const b of [
      this.centerBuf,
      this.radiusBuf,
      this.colorBuf,
      this.edgeBuf,
    ])
      gl.deleteBuffer(b);
    gl.deleteVertexArray(this.nodeVao);
    gl.deleteVertexArray(this.edgeVao);
  }
}
