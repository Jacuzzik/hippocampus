// WebGL 2 renderer for the brain graph: edges as lines, nodes as instanced quads.
import type { Camera } from "./model";

export type Rgba = [number, number, number, number];

const NODE_VS = `#version 300 es
in vec2 corner;
in vec2 center;
in float radius;
in float shape;
in vec4 color;
uniform vec3 cam;
uniform vec2 viewport;
uniform float dpr;
out vec2 v_corner;
out vec2 v_half;
flat out float v_shape;
out vec4 v_color;
void main() {
  // Tall rectangles are 0.6 wide and 1.4 high, times the radius (see SHAPE_TALL in model.ts).
  vec2 ext = shape > 1.5 ? vec2(0.6, 1.4) : vec2(1.0);
  vec2 hs = radius * ext * dpr;
  vec2 px = center * cam.x + cam.yz + corner * hs;
  vec2 clip = px / viewport * 2.0 - 1.0;
  gl_Position = vec4(clip.x, -clip.y, 0.0, 1.0);
  v_corner = corner;
  v_half = hs;
  v_shape = shape;
  v_color = color;
}`;

const NODE_FS = `#version 300 es
precision mediump float;
// highp to match the vertex shader's uniform, or the program fails to link on strict drivers.
uniform highp float dpr;
in vec2 v_corner;
in vec2 v_half;
flat in float v_shape;
in vec4 v_color;
out vec4 frag;
void main() {
  if (v_shape < 0.5) {
    float d = length(v_corner);
    if (d > 1.0) discard;
    frag = vec4(v_color.rgb, v_color.a * smoothstep(1.0, 0.8, d));
    return;
  }
  // Hollow: a 1.5 px outline just inside the box's edge, nothing inside.
  vec2 p = v_corner * v_half;
  float edge = min(v_half.x - abs(p.x), v_half.y - abs(p.y));
  float a = 1.0 - smoothstep(1.5 * dpr - 0.5, 1.5 * dpr + 0.5, edge);
  if (a <= 0.0) discard;
  frag = vec4(v_color.rgb, v_color.a * a);
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
  private readonly shapeBuf: WebGLBuffer;
  private readonly colorBuf: WebGLBuffer;
  private readonly edgeBuf: WebGLBuffer;
  private readonly focusVao: WebGLVertexArrayObject;
  private readonly focusBuf: WebGLBuffer;
  private dpr = 1;
  private nodeCount = 0;
  private edgeVertexCount = 0;
  private focusVertexCount = 0;

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
    this.shapeBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.colorBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.edgeBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));
    this.focusBuf = buffer(gl, gl.ARRAY_BUFFER, new Float32Array(0));

    this.nodeVao = this.makeVao(() => {
      const corner = buffer(gl, gl.ARRAY_BUFFER, quad);
      this.bindAttr(this.nodeProg, "corner", corner, 2, 0);
      this.bindAttr(this.nodeProg, "center", this.centerBuf, 2, 1);
      this.bindAttr(this.nodeProg, "radius", this.radiusBuf, 1, 1);
      this.bindAttr(this.nodeProg, "shape", this.shapeBuf, 1, 1);
      this.bindAttr(this.nodeProg, "color", this.colorBuf, 4, 1);
    });
    this.edgeVao = this.makeVao(() => {
      this.bindAttr(this.edgeProg, "pos", this.edgeBuf, 2, 0);
    });
    this.focusVao = this.makeVao(() => {
      this.bindAttr(this.edgeProg, "pos", this.focusBuf, 2, 0);
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

  /** `pos` is interleaved x, y per node; `lines` is world-space segments, four floats each (x1, y1, x2, y2). */
  setGraph(pos: Float32Array, lines: Float32Array): void {
    const gl = this.gl;
    this.nodeCount = pos.length / 2;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.centerBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
    this.setLines(lines);
  }

  /** Move the nodes to new positions, same count as setGraph. */
  setPositions(pos: Float32Array): void {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.centerBuf);
    this.gl.bufferSubData(this.gl.ARRAY_BUFFER, 0, pos);
  }

  /** Replace the edges with new world-space segments, four floats each. */
  setLines(lines: Float32Array): void {
    this.edgeVertexCount = lines.length / 2;
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.edgeBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, lines, this.gl.DYNAMIC_DRAW);
  }

  /** The links of the hovered or selected note, drawn in their own colour over the rest. */
  setFocusLines(lines: Float32Array): void {
    this.focusVertexCount = lines.length / 2;
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.focusBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, lines, this.gl.DYNAMIC_DRAW);
  }

  /** One radius (px) per node. */
  setRadii(radii: Float32Array): void {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.radiusBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, radii, this.gl.DYNAMIC_DRAW);
  }

  /** One shape per node: SHAPE_DISK, SHAPE_SQUARE or SHAPE_TALL from model.ts. */
  setShapes(shapes: Float32Array): void {
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.shapeBuf);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, shapes, this.gl.DYNAMIC_DRAW);
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

  draw(cam: Camera, background: Rgba, edgeColor: Rgba, focusColor: Rgba): void {
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
    if (this.focusVertexCount > 0) {
      gl.uniform4f(gl.getUniformLocation(this.edgeProg, "edgeColor"), ...focusColor);
      gl.bindVertexArray(this.focusVao);
      gl.drawArrays(gl.LINES, 0, this.focusVertexCount);
    }

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
      this.shapeBuf,
      this.colorBuf,
      this.edgeBuf,
    ])
      gl.deleteBuffer(b);
    gl.deleteVertexArray(this.nodeVao);
    gl.deleteVertexArray(this.edgeVao);
    gl.deleteBuffer(this.focusBuf);
    gl.deleteVertexArray(this.focusVao);
  }
}
