// A stateless tape model: line jitter and dropouts depend on frame + seed only.
export const vhs = `
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7)) + uSeed) * 43758.5453); }
vec2 tapeUV(vec2 uv) {
  float frame = floor(uTime * 60.0 + 0.01);
  float line = floor(uv.y * 540.0);
  float jitter = sin(uv.y * 37.0 + uTime * 1.3) * 0.00065;
  float tracking = smoothstep(0.94, 0.99, uv.y) * (hash(vec2(line,frame))-0.5) * 0.016;
  uv.x += (jitter + tracking) * uIntensity;
  return uv;
}
vec3 tapeColor(vec2 uv, vec3 color) {
  float frame = floor(uTime * 60.0 + 0.01);
  float dropout = step(0.9985, hash(vec2(floor(uv.y*540.0), floor(frame/3.0))));
  color += dropout * uIntensity * 0.15;
  float hum = exp(-pow((fract(uv.y-uTime*0.042)-0.5)*19.0, 2.0));
  color *= 1.0 - hum * 0.08 * uIntensity;
  float head = smoothstep(0.958,0.987,uv.y);
  color = mix(color,vec3(hash(vec2(floor(uv.x*460.0),frame))),head*0.2*uIntensity);
  return color;
}`;
