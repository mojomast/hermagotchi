export const staticShader = `
vec3 channelStatic(vec2 uv) {
  float frame = floor(uTime*60.0 + 0.01);
  float n = hash(vec2(floor(uv.x*640.0),floor(uv.y*360.0)) + vec2(frame*17.0,frame*3.0));
  float band = sin(uv.y*130.0+frame*2.0)*0.12;
  return vec3(clamp(n*0.85+band,0.0,1.0));
}`;

export function staticAmount(local, index) {
  if (!index) return 0;
  return local < .22 ? .92 * (1 - local / .22) : 0;
}
