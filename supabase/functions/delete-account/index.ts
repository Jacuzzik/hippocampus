// Deletes the signed-in user's Hippocampus account (14.11). Called by the app with the user's own token.
// Deploy: supabase functions deploy delete-account   (Supabase provides the two variables below itself)
import { createClient } from "jsr:@supabase/supabase-js@2.49.4";

Deno.serve(async (req: Request): Promise<Response> => {
  if (req.method !== "POST") return new Response("Use POST", { status: 405 });
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer /, "");
  const admin = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );
  // Only the owner of the token can be deleted: the user id comes from the token, never from the request.
  const { data, error } = await admin.auth.getUser(token);
  if (error || !data.user) return new Response("Not signed in", { status: 401 });
  const gone = await admin.auth.admin.deleteUser(data.user.id);
  if (gone.error) return new Response("Could not delete", { status: 500 });
  return Response.json({ deleted: true });
});
