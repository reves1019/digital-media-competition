import * as THREE from './vendor/build/three.module.js';
import { GLTFLoader } from './vendor/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from './vendor/examples/jsm/controls/OrbitControls.js';

const $ = (selector) => document.querySelector(selector);
const canvas = $('#viewport');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.setSize(innerWidth, innerHeight, false);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.88;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const world = new THREE.Scene();
world.background = new THREE.Color('#171c1d');
world.fog = new THREE.Fog('#171c1d', 48, 92);
const camera = new THREE.PerspectiveCamera(34, innerWidth / innerHeight, 0.05, 180);
const orbit = new OrbitControls(camera, canvas);
orbit.enabled = false;
orbit.enableDamping = true;
orbit.dampingFactor = 0.075;
orbit.enablePan = false;
orbit.minDistance = 7;
orbit.maxDistance = 55;
orbit.maxPolarAngle = Math.PI * 0.82;
orbit.target.set(0, 4.2, 0);

const sculptureRoot = new THREE.Group();
sculptureRoot.name = 'SnowMountainSculpture';
world.add(sculptureRoot);
const pointRoot = new THREE.Group();
pointRoot.name = 'SurfacePointCloud';
pointRoot.visible = false;
world.add(pointRoot);
const particleRoot = new THREE.Group();
particleRoot.name = 'AnimatedSculptureParticles';
particleRoot.visible = true;
world.add(particleRoot);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(100, 100),
  new THREE.MeshStandardMaterial({ color: '#121718', roughness: 0.93, metalness: 0.02 })
);
floor.rotation.x = -Math.PI / 2;
// GLTF is y-up: Blender's z-height arrives on y. Current export bottoms at about y=-2.26.
floor.position.y = -2.38;
floor.receiveShadow = true;
world.add(floor);

world.add(new THREE.HemisphereLight('#d9e0dc', '#111619', 1.15));
const key = new THREE.DirectionalLight('#e4e9e2', 2.05);
key.position.set(-13, 20, 24);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -24; key.shadow.camera.right = 24;
key.shadow.camera.top = 25; key.shadow.camera.bottom = -8;
key.shadow.bias = -0.0004;
world.add(key);
const fill = new THREE.DirectionalLight('#aab7b6', 0.58);
fill.position.set(18, 9, -22);
world.add(fill);

// White-film acceptance material: high roughness keeps relief readable while
// retaining enough value separation for the later particle pass.
const ambientMaterial = new THREE.MeshStandardMaterial({ color: '#deddd4', roughness: 0.965, metalness: 0.0 });
const pointMaterial = new THREE.PointsMaterial({ color: '#9aa7ac', size: 0.022, sizeAttenuation: true, transparent: true, opacity: 0.26, depthWrite: false });
// The Blender morph cache is five fixed-index targets (A→E), plus RGBA color,
// phase and a byte role mask. The browser keeps the white GLB as the hero layer
// and runs the point positions through a small ping-pong FBO simulation.
const MORPH_SIZE = 512;
const MORPH_COUNT = MORPH_SIZE * MORPH_SIZE;
const MORPH_SHAPES = 5;
const morphURL = new URL('../assets/snow_mountain_morph_points_512.bin', import.meta.url).href;
const morph = {
  ready: false, loading: false, failed: false, fboSupported: false, token: 0,
  targets: null, colors: null, phases: null, roles: null, targetTexture: null,
  metaTexture: null, roleTexture: null, read: null, write: null,
  simScene: null, simCamera: null, simQuad: null, simMaterial: null,
  particleCloud: null, needsReset: true
};
const particleMaterial = new THREE.ShaderMaterial({
  uniforms: {
    uPositionTex: { value: null }, uMetaTex: { value: null }, uRoleTex: { value: null },
    uProgress: { value: 0 }, uTime: { value: 0 }, uStrength: { value: 0.28 },
    uPixelRatio: { value: Math.min(devicePixelRatio || 1, 2) }, uPointSize: { value: 2.65 }
  },
  transparent: true, depthTest: false, depthWrite: false,
  blending: THREE.AdditiveBlending,
  vertexShader: `
    attribute vec2 aMorphUv;
    uniform sampler2D uPositionTex;
    uniform sampler2D uMetaTex;
    uniform sampler2D uRoleTex;
    uniform float uProgress;
    uniform float uTime;
    uniform float uStrength;
    uniform float uPixelRatio;
    uniform float uPointSize;
    varying vec3 vColor;
    varying float vAlpha;
    void main() {
      vec3 pos = texture2D(uPositionTex, aMorphUv).xyz;
      vec4 meta = texture2D(uMetaTex, aMorphUv);
      float role = texture2D(uRoleTex, aMorphUv).r * 2.0;
      float hash = fract(sin(dot(aMorphUv * 511.0 + 0.17, vec2(12.9898, 78.233))) * 43758.5453);
      // Keep every fixed index visible for the main morph. The hash only
      // modulates brightness slightly; dropping most body points would turn
      // the sculpture back into a broken outline.
      float sparse = 0.82 + 0.18 * hash;
      float phase = meta.a * 6.2831853;
      float flow = smoothstep(0.20, 0.74, uProgress);
      float pulse = sin(uTime * (0.72 + role * 0.16) + phase + pos.x * 0.22);
      pos += vec3(cos(phase * 0.71), sin(phase * 0.53), cos(phase * 0.37)) * pulse * 0.025 * flow;
      vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
      gl_Position = projectionMatrix * mvPosition;
      gl_PointSize = clamp(uPointSize * uPixelRatio * (39.0 / max(5.0, -mvPosition.z)) * (1.0 + role * 0.18), 1.35, 7.2);
      vColor = meta.rgb;
      float inFade = 0.65 + 0.35 * smoothstep(0.0, 0.055, uProgress);
      float outFade = 1.0 - smoothstep(0.84, 1.0, uProgress) * 0.58;
      float roleGain = role > 1.5 ? 1.35 : (role > 0.5 ? 0.72 : 0.42);
      vAlpha = min(0.58, uStrength * roleGain * sparse * inFade * outFade);
    }
  `,
  fragmentShader: `
    varying vec3 vColor;
    varying float vAlpha;
    void main() {
      float d = distance(gl_PointCoord, vec2(0.5));
      float soft = 1.0 - smoothstep(0.16, 0.5, d);
      if (soft < 0.01) discard;
      gl_FragColor = vec4(vColor, vAlpha * soft);
    }
  `
});
const loader = new GLTFLoader();
const modelURL = new URL('../assets/snow_mountain_sculpture.glb', import.meta.url).href;
const reducedMotionQuery = matchMedia('(prefers-reduced-motion: reduce)');
const curves = {
  position: new THREE.CatmullRomCurve3([
    new THREE.Vector3(1, 13, 30), new THREE.Vector3(-3, 6.7, 10), new THREE.Vector3(7, 10.8, 10), new THREE.Vector3(7, 15, 30)
  ], false, 'centripetal'),
  target: new THREE.CatmullRomCurve3([
    new THREE.Vector3(0, 4.4, 0), new THREE.Vector3(-3, 4, 0), new THREE.Vector3(5.5, 7.2, 0), new THREE.Vector3(1, 4.3, 0)
  ], false, 'centripetal')
};
const captions = [
  { title: '雪线之上', copy: '总览整件白膜雕塑' },
  { title: '向山脊靠近', copy: '中段人物与岩层转折' },
  { title: '与人物同行', copy: '先看形体，再叠加粒子' },
  { title: '回望长路', copy: '保持主体轮廓清楚' }
];
let mode = 'scroll';
let scrollTarget = 0, scrollProgress = 0;
let currentModel = null, pointCloud = null, particleCloud = null, modelReady = false, modelFailed = false;
let pointBuildToken = 0;
let particleBuildToken = 0;
let reducedMotion = reducedMotionQuery.matches;
let lastTime = 0, lastUI = -1;
let particleEnabled = true, particleStrength = 0.28, whiteFilmEnabled = true;
const info = { meshes: 0, vertices: 0, triangles: 0, dimensions: null };

function setStatus(text, state = '') {
  $('#model-state span').textContent = text;
  $('#model-state').className = `model-state ${state}`;
}

function formatBytes(bytes) {
  if (!bytes) return '—';
  return bytes < 1048576 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1048576).toFixed(1)} MB`;
}

function updateFacts() {
  const facts = $('#model-facts').querySelectorAll('dd');
  facts[0].textContent = modelReady ? 'snow_mountain_sculpture.glb' : '尚未载入';
  facts[1].textContent = modelReady ? `${info.meshes} 个网格 · ${Math.round(info.triangles).toLocaleString()} 三角面` : '—';
  facts[2].textContent = info.dimensions ? `${info.dimensions.x.toFixed(1)} × ${info.dimensions.y.toFixed(1)} × ${info.dimensions.z.toFixed(1)}` : '—';
}

function applyPlasterMaterial(root) {
  root.traverse(object => {
    if (!object.isMesh) return;
    object.castShadow = true; object.receiveShadow = true;
    object.material = ambientMaterial.clone();
  });
}

function inspectModel(root) {
  const box = new THREE.Box3().setFromObject(root);
  const size = box.getSize(new THREE.Vector3());
  info.dimensions = size;
  if (Number.isFinite(box.min.y)) floor.position.y = box.min.y + 0.02;
  info.meshes = 0; info.vertices = 0; info.triangles = 0;
  root.traverse(object => {
    if (!object.isMesh || !object.geometry) return;
    info.meshes++;
    const position = object.geometry.getAttribute('position');
    if (position) info.vertices += position.count;
    info.triangles += object.geometry.index ? object.geometry.index.count / 3 : (position?.count || 0) / 3;
  });
}

function buildPointCloud(root, token) {
  const points = [];
  const random = (() => { let seed = 0x7f4a7c15; return () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; })();
  const worldMatrix = new THREE.Matrix4();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  const face = new THREE.Triangle();
  root.updateMatrixWorld(true);
  root.traverse(object => {
    if (!object.isMesh || !object.geometry?.getAttribute('position')) return;
    const geometry = object.geometry;
    const position = geometry.getAttribute('position');
    const index = geometry.index;
    worldMatrix.copy(object.matrixWorld);
    const count = index ? index.count / 3 : position.count / 3;
    const stride = Math.max(1, Math.ceil((info.triangles || count) / 50000));
    for (let triangle = 0; triangle < count; triangle += stride) {
      const ia = index ? index.getX(triangle * 3) : triangle * 3;
      const ib = index ? index.getX(triangle * 3 + 1) : triangle * 3 + 1;
      const ic = index ? index.getX(triangle * 3 + 2) : triangle * 3 + 2;
      a.fromBufferAttribute(position, ia).applyMatrix4(worldMatrix);
      b.fromBufferAttribute(position, ib).applyMatrix4(worldMatrix);
      c.fromBufferAttribute(position, ic).applyMatrix4(worldMatrix);
      face.set(a, b, c);
      const area = face.getArea();
      const samples = Math.max(1, Math.min(8, Math.ceil(area * 0.9)));
      for (let sample = 0; sample < samples && points.length < 50000; sample++) {
        let u = random(), v = random(); if (u + v > 1) { u = 1 - u; v = 1 - v; }
        points.push(a.clone().multiplyScalar(1 - u - v).addScaledVector(b, u).addScaledVector(c, v));
      }
      if (points.length >= 50000) break;
    }
  });
  if (token !== pointBuildToken) return;
  const positions = new Float32Array(points.length * 3);
  points.forEach((point, index) => point.toArray(positions, index * 3));
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  pointCloud = new THREE.Points(geometry, pointMaterial);
  pointCloud.name = 'SampledSurfacePoints'; pointRoot.add(pointCloud);
  $('#points-toggle').dataset.count = String(points.length);
}

function floatTexture(data, width, height) {
  const texture = new THREE.DataTexture(data, width, height, THREE.RGBAFormat, THREE.FloatType);
  texture.minFilter = THREE.NearestFilter; texture.magFilter = THREE.NearestFilter;
  texture.wrapS = THREE.ClampToEdgeWrapping; texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.flipY = false; texture.generateMipmaps = false; texture.colorSpace = THREE.NoColorSpace;
  texture.needsUpdate = true;
  return texture;
}

function disposeMorphResources() {
  if (particleCloud) { particleRoot.remove(particleCloud); particleCloud.geometry.dispose(); particleCloud = null; }
  if (morph.simQuad) { morph.simQuad.geometry.dispose(); morph.simMaterial?.dispose(); morph.simQuad = null; morph.simScene = null; morph.simCamera = null; morph.simMaterial = null; }
  [morph.targetTexture, morph.metaTexture, morph.roleTexture].forEach(texture => texture?.dispose());
  [morph.read, morph.write].forEach(target => target?.dispose());
  morph.targetTexture = morph.metaTexture = morph.roleTexture = null;
  morph.read = morph.write = null; morph.ready = false; morph.fboSupported = false;
}

async function buildParticleLayer(root, token) {
  morph.loading = true; morph.failed = false; morph.ready = false;
  $('#particle-toggle').disabled = true;
  try {
    const response = await fetch(morphURL, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`morph cache HTTP ${response.status}`);
    const buffer = await response.arrayBuffer();
    if (token !== particleBuildToken) return;
    const expectedBytes = (MORPH_SHAPES * MORPH_COUNT * 3 + MORPH_COUNT * 4 + MORPH_COUNT) * 4 + MORPH_COUNT;
    if (buffer.byteLength < expectedBytes) throw new Error(`morph cache is ${buffer.byteLength} bytes; expected ${expectedBytes}`);
    const floats = new Float32Array(buffer, 0, MORPH_SHAPES * MORPH_COUNT * 3 + MORPH_COUNT * 4 + MORPH_COUNT);
    const colorFloatOffset = MORPH_SHAPES * MORPH_COUNT * 3;
    const phaseFloatOffset = colorFloatOffset + MORPH_COUNT * 4;
    const roleByteOffset = (phaseFloatOffset + MORPH_COUNT) * 4;
    const colors = new Float32Array(buffer, colorFloatOffset * 4, MORPH_COUNT * 4);
    const phases = new Float32Array(buffer, phaseFloatOffset * 4, MORPH_COUNT);
    const roles = new Uint8Array(buffer, roleByteOffset, MORPH_COUNT);
    // Atlas rows: each 512x512 layer is one target shape. RGBA is used even
    // though the source stores XYZ so the texture is uploadable as RGBA32F.
    const targetData = new Float32Array(MORPH_COUNT * MORPH_SHAPES * 4);
    for (let shape = 0; shape < MORPH_SHAPES; shape++) {
      const sourceOffset = shape * MORPH_COUNT * 3;
      const targetOffset = shape * MORPH_COUNT * 4;
      for (let i = 0; i < MORPH_COUNT; i++) {
        const s = sourceOffset + i * 3; const d = targetOffset + i * 4;
        // Blender samples are Z-up. GLTFLoader presents the exported GLB as
        // Y-up, so apply the same axis handoff here: (x, z, -y).
        targetData[d] = floats[s]; targetData[d + 1] = floats[s + 2]; targetData[d + 2] = -floats[s + 1]; targetData[d + 3] = 1;
      }
    }
    const metaData = new Float32Array(MORPH_COUNT * 4);
    const roleData = new Float32Array(MORPH_COUNT * 4);
    for (let i = 0; i < MORPH_COUNT; i++) {
      const d = i * 4;
      metaData[d] = colors[d]; metaData[d + 1] = colors[d + 1]; metaData[d + 2] = colors[d + 2];
      metaData[d + 3] = ((phases[i] / (Math.PI * 2)) % 1 + 1) % 1;
      roleData[d] = roles[i] / 2; roleData[d + 3] = 1;
    }
    disposeMorphResources();
    morph.targets = targetData; morph.colors = colors; morph.phases = phases; morph.roles = roles;
    morph.targetTexture = floatTexture(targetData, MORPH_SIZE, MORPH_SIZE * MORPH_SHAPES);
    morph.metaTexture = floatTexture(metaData, MORPH_SIZE, MORPH_SIZE);
    morph.roleTexture = floatTexture(roleData, MORPH_SIZE, MORPH_SIZE);
    const uv = new Float32Array(MORPH_COUNT * 2); const zeroPositions = new Float32Array(MORPH_COUNT * 3);
    for (let y = 0; y < MORPH_SIZE; y++) for (let x = 0; x < MORPH_SIZE; x++) {
      const i = y * MORPH_SIZE + x; uv[i * 2] = (x + 0.5) / MORPH_SIZE; uv[i * 2 + 1] = (y + 0.5) / MORPH_SIZE;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(zeroPositions, 3));
    geometry.setAttribute('aMorphUv', new THREE.BufferAttribute(uv, 2));
    particleCloud = new THREE.Points(geometry, particleMaterial);
    particleCloud.name = 'GpuMorphParticles512'; particleCloud.frustumCulled = false; particleCloud.renderOrder = 10;
    particleRoot.add(particleCloud);
    particleMaterial.uniforms.uMetaTex.value = morph.metaTexture;
    particleMaterial.uniforms.uRoleTex.value = morph.roleTexture;

    // Float texture sampling alone does not guarantee a renderable Float FBO.
    morph.fboSupported = renderer.extensions.has('EXT_color_buffer_float');
    if (!morph.fboSupported) throw new Error('当前浏览器没有可写入 Float FBO 的 WebGL 能力');
    const targetOptions = { type: THREE.FloatType, format: THREE.RGBAFormat, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.ClampToEdgeWrapping, depthBuffer: false, stencilBuffer: false };
    morph.read = new THREE.WebGLRenderTarget(MORPH_SIZE, MORPH_SIZE, targetOptions);
    morph.write = new THREE.WebGLRenderTarget(MORPH_SIZE, MORPH_SIZE, targetOptions);
    morph.simScene = new THREE.Scene(); morph.simCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    morph.simMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uPrevious: { value: null }, uTargets: { value: morph.targetTexture }, uLayerA: { value: 0 }, uLayerB: { value: 1 },
        uLocal: { value: 0 }, uDelta: { value: 0.016 }, uSnap: { value: 1 }
      }, depthTest: false, depthWrite: false,
      vertexShader: 'varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }',
      fragmentShader: `
        uniform sampler2D uPrevious; uniform sampler2D uTargets;
        uniform float uLayerA; uniform float uLayerB; uniform float uLocal; uniform float uDelta; uniform float uSnap;
        varying vec2 vUv;
        vec3 readTarget(float layer){ return texture2D(uTargets, vec2(vUv.x, (vUv.y + layer) / 5.0)).xyz; }
        void main(){
          vec3 goal = mix(readTarget(uLayerA), readTarget(uLayerB), uLocal);
          vec3 previous = texture2D(uPrevious, vUv).xyz;
          float blend = uSnap > 0.5 ? 1.0 : (1.0 - exp(-max(0.001, uDelta) * 14.0));
          gl_FragColor = vec4(mix(previous, goal, blend), 1.0);
        }
      `
    });
    morph.simQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), morph.simMaterial); morph.simScene.add(morph.simQuad);
    morph.needsReset = true; morph.ready = true; morph.loading = false; morph.failed = false;
    particleMaterial.uniforms.uPositionTex.value = morph.read.texture;
    $('#particle-toggle').dataset.count = String(MORPH_COUNT); $('#particle-toggle').disabled = false;
    setStatus('GLB 与 GPU 粒子已载入', 'loaded');
  } catch (error) {
    disposeMorphResources();
    morph.loading = false; morph.failed = true; morph.ready = false;
    $('#particle-toggle').disabled = true;
    console.error('[Sculpture viewer] morph particle load failed', error);
  }
}

function updateMorphSimulation(dt, progress) {
  if (!morph.ready || !morph.read || !morph.write || !morph.simMaterial) return;
  const scaled = Math.min(3.99999, Math.max(0, progress) * (MORPH_SHAPES - 1));
  const layerA = Math.floor(scaled); const layerB = Math.min(MORPH_SHAPES - 1, layerA + 1);
  morph.simMaterial.uniforms.uPrevious.value = morph.read.texture;
  morph.simMaterial.uniforms.uLayerA.value = layerA; morph.simMaterial.uniforms.uLayerB.value = layerB; morph.simMaterial.uniforms.uLocal.value = scaled - layerA;
  morph.simMaterial.uniforms.uDelta.value = dt; morph.simMaterial.uniforms.uSnap.value = (morph.needsReset || reducedMotion) ? 1 : 0;
  renderer.setRenderTarget(morph.write); renderer.render(morph.simScene, morph.simCamera); renderer.setRenderTarget(null);
  const swap = morph.read; morph.read = morph.write; morph.write = swap; morph.needsReset = false;
  particleMaterial.uniforms.uPositionTex.value = morph.read.texture;
}

function loadModel() {
  modelFailed = false; $('#error').hidden = true; $('#retry').hidden = true;
  $('#loading').classList.remove('done'); $('#loading-fill').style.width = '0%';
  $('#loading-text').textContent = '正在读取雪山雕塑 · 0%'; setStatus('读取 GLB');
  loader.load(modelURL, result => {
    currentModel = result.scene;
    applyPlasterMaterial(currentModel); sculptureRoot.add(currentModel);
    inspectModel(currentModel); modelReady = true; updateFacts(); setStatus('GLB 已载入', 'loaded');
    $('#loading-fill').style.width = '100%'; $('#loading-text').textContent = '模型已载入 · 可开始检查镜头';
    setTimeout(() => $('#loading').classList.add('done'), 520);
    pointBuildToken++; buildPointCloud(currentModel, pointBuildToken); $('#points-toggle').disabled = false;
    particleBuildToken++; buildParticleLayer(currentModel, particleBuildToken);
  }, progress => {
    const total = progress.total || 0; const percent = total ? Math.min(99, progress.loaded / total * 100) : 0;
    $('#loading-fill').style.width = `${percent}%`; $('#loading-text').textContent = total ? `正在读取雪山雕塑 · ${Math.round(percent)}%` : `正在读取雪山雕塑 · ${formatBytes(progress.loaded)}`;
  }, error => {
    modelFailed = true; setStatus('等待 GLB', 'failed'); $('#loading').classList.add('done'); $('#error').hidden = false;
    $('#error-text').textContent = `未找到 ${modelURL.split('/').pop()}。请将 Blender 导出的文件放入 snow-benchmark/assets/。`;
    console.error('[Sculpture viewer] GLB load failed', error);
  });
}

function updateScroll() { scrollTarget = Math.max(0, Math.min(1, scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight))); }
function setCameraFromProgress(value, immediate = false) {
  const position = curves.position.getPoint(Math.max(0, Math.min(1, value)));
  const target = curves.target.getPoint(Math.max(0, Math.min(1, value)));
  if (immediate) camera.position.copy(position); else camera.position.lerp(position, 0.28);
  camera.lookAt(target);
}
function updateCaption(value) {
  const segment = value < 0.333 ? 0 : value < 0.667 ? 1 : value < 0.85 ? 2 : 3;
  const shotButtons = document.querySelectorAll('.shot');
  shotButtons.forEach((button, index) => button.classList.toggle('active', index === segment));
  shotButtons.forEach((button, index) => button.setAttribute('aria-current', String(index === segment)));
  const caption = captions[segment]; $('#view-copy').textContent = caption.copy; $('h1').textContent = caption.title;
  const percent = Math.round(value * 100); $('#progress-value').textContent = String(percent).padStart(2, '0');
}
function tick(time) {
  const dt = Math.min(.05, Math.max(0, (time - (lastTime || time)) / 1000)); lastTime = time;
  if (mode === 'scroll') {
    scrollProgress = reducedMotion ? scrollTarget : scrollProgress + (scrollTarget - scrollProgress) * (1 - Math.exp(-9 * dt));
    setCameraFromProgress(scrollProgress, reducedMotion);
    if (time - lastUI > 70) { updateCaption(scrollProgress); lastUI = time; }
  } else orbit.update();
  updateMorphSimulation(dt, scrollProgress);
  particleMaterial.uniforms.uProgress.value = reducedMotion ? 0.32 : scrollProgress;
  particleMaterial.uniforms.uTime.value = reducedMotion ? 0 : time / 1000;
  particleMaterial.uniforms.uStrength.value = particleEnabled ? particleStrength : 0;
  renderer.render(world, camera); requestAnimationFrame(tick);
}

function setMode(nextMode) {
  mode = nextMode; document.body.classList.toggle('free-active', mode === 'free');
  orbit.enabled = mode === 'free';
  document.querySelectorAll('[data-mode]').forEach(button => { const active = button.dataset.mode === mode; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
  if (mode === 'free') { orbit.saveState(); orbit.target.set(0, 4.2, 0); orbit.update(); }
  else { updateScroll(); scrollProgress = scrollTarget; setCameraFromProgress(scrollProgress, true); updateCaption(scrollProgress); }
}
function resetCamera() {
  if (mode === 'free') { camera.position.set(2, 9, 30); orbit.target.set(0, 4, 0); orbit.update(); }
  else { window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' }); scrollTarget = 0; }
}

addEventListener('scroll', updateScroll, { passive: true });
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); const pixelRatio = Math.min(devicePixelRatio || 1, 2); renderer.setSize(innerWidth, innerHeight, false); renderer.setPixelRatio(pixelRatio); particleMaterial.uniforms.uPixelRatio.value = pixelRatio; updateScroll(); }, { passive: true });
addEventListener('keydown', event => { if (event.key === 'Escape' && !$('#info-drawer').hidden) toggleInfo(false); });
document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));
document.querySelectorAll('[data-progress]').forEach(button => button.addEventListener('click', () => { setMode('scroll'); const value = Number(button.dataset.progress); window.scrollTo({ top: value * (document.documentElement.scrollHeight - innerHeight), behavior: reducedMotion ? 'auto' : 'smooth' }); }));
$('#reset-camera').addEventListener('click', resetCamera);
$('#points-toggle').addEventListener('click', event => {
  const active = pointRoot.visible = !pointRoot.visible;
  // Keep the white-film mesh visible. The particle layer is an overlay, so
  // silhouettes and sculpted faces remain readable during the effect.
  sculptureRoot.visible = whiteFilmEnabled;
  event.currentTarget.setAttribute('aria-pressed', String(active));
  event.currentTarget.querySelector('span').textContent = active ? '点云 · 叠加' : '表面点云';
});
$('#particle-toggle').addEventListener('click', event => {
  particleEnabled = !particleEnabled;
  event.currentTarget.setAttribute('aria-pressed', String(particleEnabled));
  event.currentTarget.querySelector('span').textContent = particleEnabled ? '彩色粒子 · 开' : '彩色粒子';
});
$('#white-film-toggle').addEventListener('click', event => {
  whiteFilmEnabled = !whiteFilmEnabled;
  sculptureRoot.visible = whiteFilmEnabled;
  event.currentTarget.setAttribute('aria-pressed', String(whiteFilmEnabled));
  event.currentTarget.querySelector('span').textContent = whiteFilmEnabled ? '白膜 · 开' : '白膜 · 隐藏';
});
$('#particle-strength').addEventListener('input', event => {
  particleStrength = Number(event.target.value) / 100;
  $('#particle-value').textContent = `${Math.round(particleStrength * 100)}%`;
});
function toggleInfo(open) { $('#info-drawer').hidden = !open; $('#production-info').setAttribute('aria-expanded', String(open)); if (open) $('#close-info').focus(); else $('#production-info').focus(); }
$('#production-info').addEventListener('click', () => toggleInfo($('#info-drawer').hidden)); $('#close-info').addEventListener('click', () => toggleInfo(false));
$('#retry').addEventListener('click', loadModel); $('#error-retry').addEventListener('click', loadModel);
reducedMotionQuery.addEventListener('change', event => { reducedMotion = event.matches; if (reducedMotion) { orbit.enableDamping = false; } else orbit.enableDamping = true; });

setStatus('等待 GLB'); updateScroll(); setCameraFromProgress(0, true); loadModel(); requestAnimationFrame(tick);
window.__sculptureViewer = Object.freeze({
  getState: () => ({ modelURL, morphURL, mode, modelReady, modelFailed, morphReady: morph.ready, morphFailed: morph.failed, fboSupported: morph.fboSupported, scrollTarget, scrollProgress, particleEnabled, particleStrength, whiteFilmEnabled, particleCount: particleCloud ? particleCloud.geometry.getAttribute('position').count : 0, pointCloud: pointCloud ? pointCloud.geometry.getAttribute('position').count : 0, meshes: info.meshes, vertices: info.vertices, triangles: info.triangles, dimensions: info.dimensions ? { x: info.dimensions.x, y: info.dimensions.y, z: info.dimensions.z } : null }),
  setProgress: (value) => { setMode('scroll'); const next = Math.max(0, Math.min(1, Number(value) || 0)); window.scrollTo({ top: next * (document.documentElement.scrollHeight - innerHeight), behavior: 'auto' }); }
});
