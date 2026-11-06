import { vhs } from './vhs.js';
import { staticShader } from './static.js';

// One full-frame WebGL2 pass. Spatial echo is sampled from this frame, never a
// previous-frame buffer: reverse seeking and distributed capture are identical.
export function createCRT(canvas, source, settings) {
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false, preserveDrawingBuffer: true });
  if (!gl) throw new Error('WebGL2 is required for the broadcast CRT treatment.');
  const vertex = `#version 300 es
in vec2 position; out vec2 uv;
void main(){ uv=vec2(position.x*.5+.5,.5-position.y*.5); gl_Position=vec4(position,0.,1.); }`;
  const fragment = `#version 300 es
precision highp float;
in vec2 uv; out vec4 outColor;
uniform sampler2D screenTexture;
uniform float uTime, uIntensity, uSeed, uStatic;
${vhs}
${staticShader}
void main() {
  vec2 p=uv*2.0-1.0;
  vec2 q=p*(1.0+0.043*uIntensity*vec2(p.y*p.y,p.x*p.x));
  vec2 st=tapeUV(q*.5+.5);
  if(any(lessThan(st,vec2(0.0)))||any(greaterThan(st,vec2(1.0)))) {outColor=vec4(.006,.005,.009,1.);return;}
  vec2 px=vec2(1.0/1920.0,1.0/1080.0);
  float bleed=1.5*uIntensity;
  vec3 c=vec3(texture(screenTexture,st+vec2(px.x*bleed,0)).r,texture(screenTexture,st).g,texture(screenTexture,st-vec2(px.x*bleed,0)).b);
  vec3 glow=vec3(0.0);
  glow+=texture(screenTexture,st+px*vec2(3,0)).rgb;
  glow+=texture(screenTexture,st+px*vec2(-3,0)).rgb;
  glow+=texture(screenTexture,st+px*vec2(0,3)).rgb;
  glow+=texture(screenTexture,st+px*vec2(0,-3)).rgb;
  c+=max(glow*.25-.52,0.0)*.24*uIntensity;
  c=mix(c,texture(screenTexture,st-vec2(.004,0)).rgb,.035*uIntensity);
  float scan=.5+.5*sin(st.y*1080.0*3.14159265);
  c*=1.0-.16*uIntensity*scan;
  float cell=mod(floor(gl_FragCoord.x),3.0);
  vec3 phosphor=cell<1.0?vec3(1.0,.83,.83):(cell<2.0?vec3(.83,1.0,.83):vec3(.83,.83,1.0));
  c*=mix(vec3(1.0),phosphor,.28*uIntensity);
  c=tapeColor(st,c);
  c=mix(c,channelStatic(st),uStatic);
  c*=1.0-.21*uIntensity*pow(length(p)*.68,3.0);
  c+=.008*uIntensity;
  outColor=vec4(c,1.0);
}`;
  const compile = (kind, text) => {
    const shader = gl.createShader(kind); gl.shaderSource(shader,text); gl.compileShader(shader);
    if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  };
  const program=gl.createProgram();
  gl.attachShader(program,compile(gl.VERTEX_SHADER,vertex));
  gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fragment)); gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
  const pos=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
  const uniforms=Object.fromEntries(['uTime','uIntensity','uSeed','uStatic'].map(k=>[k,gl.getUniformLocation(program,k)]));
  return {
    draw(time, burst) {
      gl.useProgram(program);gl.bindTexture(gl.TEXTURE_2D,texture);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
      gl.uniform1f(uniforms.uTime,time);gl.uniform1f(uniforms.uIntensity,Math.max(0,Math.min(1,settings.effectIntensity)));
      gl.uniform1f(uniforms.uSeed,settings.seed);gl.uniform1f(uniforms.uStatic,burst);
      gl.viewport(0,0,canvas.width,canvas.height);gl.drawArrays(gl.TRIANGLES,0,6);gl.finish();
    },
    dispose(){gl.deleteTexture(texture);gl.deleteBuffer(buffer);gl.deleteProgram(program);}
  };
}
