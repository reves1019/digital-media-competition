const $ = (selector) => document.querySelector(selector);
const scene = $('#scene');
const ctx = scene.getContext('2d', { alpha: false });
const atmosphere = $('#atmosphere');
const sky = atmosphere.getContext('2d');
const progressInput = $('#scene-progress');
const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
const manifestURL = new URL('../assets/manifest.json', import.meta.url);
const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const smooth = (value) => { const x = clamp(value); return x * x * (3 - 2 * x); };
const images = new Map();
const pending = new Set();
const failed = new Set();
const seen = new Set();
const queue = [];
let manifest, urls = [], poster, captions = [], currentCaption = -1;
let target = 0, progress = 0, tour = false, tourProgress = 0, tourDuration = 36;
let reducedMotion = motionQuery.matches, snowLevel = 0.22, ready = false, dotsEnabled = true;
let width = 0, height = 0, dpr = 1, activeLoads = 0, cacheLimit = 36;
let lastTime = 0, lastSnowTime = 0, lastFrame = -1, lastMix = -1, lastDemand = -1;
let lastUI = 0, maxScroll = 1, renderDirty = true, shownError = false;
const particleSampleCanvas = document.createElement('canvas');
particleSampleCanvas.width = 72; particleSampleCanvas.height = 41;
const particleSample = particleSampleCanvas.getContext('2d', { willReadFrequently: true });
let dotCache = new Map();
const snow = Array.from({ length: 150 }, (_, i) => ({
  x: ((i * 0.618033988749895) % 1), y: ((i * 0.414213562373095) % 1),
  z: 0.2 + ((i * 0.732050807568877) % 1) * 0.8,
  phase: i * 2.17
}));

function updateScroll() { target = clamp(window.scrollY / maxScroll); }
function resize() {
  width = innerWidth; height = innerHeight; dpr = Math.min(devicePixelRatio || 1, 1.75);
  for (const canvas of [scene, atmosphere]) {
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
  }
  dotCache.clear();
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); sky.setTransform(dpr, 0, 0, dpr, 0, 0);
  maxScroll = Math.max(1, document.documentElement.scrollHeight - height);
  updateScroll(); renderDirty = true;
}

function stopTour() {
  tour = false;
  $('#tour').setAttribute('aria-pressed', 'false');
  $('#tour-label').textContent = '自动演绎';
}
function seek(value) {
  stopTour(); target = clamp(value);
  window.scrollTo({ top: target * maxScroll, behavior: 'instant' });
}

function requestFrame(index, priority = false) {
  if (index < 0 || index >= urls.length || images.has(index) || pending.has(index) || failed.has(index)) return;
  pending.add(index);
  if (priority) queue.unshift(index); else queue.push(index);
}

function pump() {
  while (activeLoads < 4 && queue.length) {
    const index = queue.shift(); activeLoads++;
    const img = new Image(); img.decoding = 'async';
    img.onload = async () => {
      try { await img.decode(); } catch { /* onload already confirms a decodable image on older browsers */ }
      images.set(index, img); seen.add(index); pending.delete(index); activeLoads--;
      renderDirty = true;
      evict(); updateLoading(); pump();
    };
    img.onerror = () => {
      pending.delete(index); failed.add(index); activeLoads--;
      updateLoading(); pump();
    };
    img.src = urls[index];
  }
}

function evict() {
  if (images.size <= cacheLimit) return;
  const center = Math.round(progress * Math.max(0, urls.length - 1));
  const candidates = [...images.keys()].sort((a, b) => Math.abs(b - center) - Math.abs(a - center));
  while (images.size > cacheLimit && candidates.length) images.delete(candidates.shift());
}

function demand(position) {
  if (!urls.length) return;
  const center = Math.round(position * (urls.length - 1));
  if (center === lastDemand && !failed.size) return;
  lastDemand = center;
  // Reprioritize the desired frame after a large jump; only in-flight requests remain ahead of it.
  const queued = queue.splice(0); for (const index of queued) pending.delete(index);
  requestFrame(center, true);
  const ahead = target >= progress ? 1 : -1;
  for (let step = 1; step <= 12; step++) {
    requestFrame(center + step * ahead); requestFrame(center - step * ahead);
  }
  // Adjacent interpolation partner and distant narrative anchors load before idle fill.
  requestFrame(Math.min(urls.length - 1, Math.floor(position * (urls.length - 1)) + 1));
  for (const anchor of [0, 0.32, 0.64, 1]) requestFrame(Math.round(anchor * (urls.length - 1)));
  if (urls.length <= cacheLimit) for (let i = 0; i < urls.length; i++) requestFrame(i);
  pump();
}

function updateLoading() {
  const loaded = seen.size;
  $('#loading-fill').style.width = `${urls.length ? loaded / urls.length * 100 : 0}%`;
  if (images.size && !ready) {
    ready = true; $('#loading').classList.add('loaded'); document.body.classList.add('ready');
  }
  if (!ready && failed.size && activeLoads === 0 && !queue.length) {
    showError('渲染帧暂未就绪。请确认 assets/frames 中已有帧文件，然后重新装载。');
  }
}

function showError(message) {
  shownError = true;
  $('#loading').classList.remove('loaded');
  $('#loading-message').textContent = message;
  $('#retry').hidden = false;
}

function imageRect(image) {
  const imageRatio = image.naturalWidth / image.naturalHeight;
  const displayRatio = width / height;
  // Preserve the procession on narrow screens; allow at most 12% crop on desktop.
  const wouldCrop = Math.max(imageRatio / displayRatio, displayRatio / imageRatio);
  const cover = width > 760 && wouldCrop < 1.14;
  const scale = cover ? Math.max(width / image.naturalWidth, height / image.naturalHeight)
    : Math.min(width / image.naturalWidth, height / image.naturalHeight);
  const w = image.naturalWidth * scale, h = image.naturalHeight * scale;
  const y = width <= 760 ? Math.max(90, (height * 0.62 - h) / 2) : (height - h) / 2;
  return [(width - w) / 2, y, w, h];
}

function drawScene() {
  const frame = progress * Math.max(0, urls.length - 1);
  const lower = Math.floor(frame), upper = Math.min(urls.length - 1, lower + 1);
  let image = images.get(lower), index = lower;
  if (!image) {
    const nearest = [...images.keys()].sort((a, b) => Math.abs(a - frame) - Math.abs(b - frame))[0];
    image = images.get(nearest); index = nearest ?? -1;
  }
  if (!image) image = poster;
  const second = images.get(upper), mix = second && index === lower ? frame - lower : 0;
  if (!renderDirty && lastFrame === index && Math.abs(mix - lastMix) < 0.012) return;
  ctx.globalAlpha = 1; ctx.fillStyle = '#16212a'; ctx.fillRect(0, 0, width, height);
  if (image?.naturalWidth) ctx.drawImage(image, ...imageRect(image));
  if (second && mix > 0.005 && index === lower) { ctx.globalAlpha = mix; ctx.drawImage(second, ...imageRect(second)); }
  ctx.globalAlpha = 1; lastFrame = index; lastMix = mix; renderDirty = false;
  document.documentElement.dataset.frame = String(index);
}

function drawSnow(time) {
  if (time - lastSnowTime < 32) return; lastSnowTime = time;
  sky.clearRect(0, 0, width, height);
  if (reducedMotion || !snowLevel || !ready) return;
  const seconds = time / 1000;
  const count = Math.round(snow.length * snowLevel);
  for (let i = 0; i < count; i++) {
    const p = snow[i];
    const x = ((p.x + seconds * 0.025 * p.z + Math.sin(seconds * 0.13 + p.phase) * 0.025) % 1) * width;
    const y = ((p.y + seconds * 0.038 * p.z) % 1) * height;
    const radius = 0.4 + p.z * 1.1;
    sky.fillStyle = `rgba(222,235,236,${0.11 + p.z * 0.24})`;
    sky.beginPath(); sky.ellipse(x, y, radius * 1.4, radius * 0.6, 0.5, 0, Math.PI * 2); sky.fill();
  }
  if (dotsEnabled) drawPointParticles(time);
}

function makePointParticles(index, image) {
  if (!image?.naturalWidth) return [];
  const rect = imageRect(image);
  particleSample.clearRect(0, 0, particleSampleCanvas.width, particleSampleCanvas.height);
  particleSample.drawImage(image, rect[0] * particleSampleCanvas.width / width, rect[1] * particleSampleCanvas.height / height, rect[2] * particleSampleCanvas.width / width, rect[3] * particleSampleCanvas.height / height);
  const data = particleSample.getImageData(0, 0, particleSampleCanvas.width, particleSampleCanvas.height).data;
  const points = [];
  for (let y = 1; y < particleSampleCanvas.height - 1; y++) for (let x = 1; x < particleSampleCanvas.width - 1; x++) {
    const i = (y * particleSampleCanvas.width + x) * 4;
    const r = data[i], g = data[i + 1], b = data[i + 2], lum = (r * .2126 + g * .7152 + b * .0722) / 255;
    const redSignal = r / 255 - (g + b) / 510;
    const leftLum = (data[i - 4] * .2126 + data[i - 3] * .7152 + data[i - 2] * .0722) / 255;
    const edge = Math.abs(lum - leftLum) + Math.abs(lum - (data[i + 4] * .2126 + data[i + 5] * .7152 + data[i + 6] * .0722) / 255);
    const weight = Math.max(0, lum * .43 + edge * .9 + Math.max(0, redSignal) * .85 - .24);
    const seed = (x * 17 + y * 31 + index * 7) % 101;
    if (weight > .08 && seed < Math.min(82, weight * 110)) points.push({ x: (x + .5) / particleSampleCanvas.width * width, y: (y + .5) / particleSampleCanvas.height * height, lum, red: Math.max(0, redSignal), size: .35 + Math.min(2, weight * 1.7), phase: (x * 13 + y * 7) % 31 });
  }
  return points;
}

function drawPointParticles(time) {
  const frame = lastFrame;
  if (frame < 0) return;
  const image = images.get(frame) || poster;
  if (!image?.naturalWidth) return;
  let points = dotCache.get(frame);
  if (!points) { points = makePointParticles(frame, image); dotCache.set(frame, points); if (dotCache.size > 14) dotCache.delete(dotCache.keys().next().value); }
  const drift = reducedMotion ? 0 : time / 1000;
  for (const point of points) {
    const sway = Math.sin(drift * .45 + point.phase) * (0.35 + point.lum * .65);
    const alpha = Math.min(.42, .075 + point.lum * .16 + point.red * .23) * snowLevel / .22;
    sky.fillStyle = point.red > .08 ? `rgba(213,112,98,${alpha})` : `rgba(224,238,235,${alpha})`;
    sky.beginPath(); sky.arc(point.x + sway, point.y, point.size, 0, Math.PI * 2); sky.fill();
  }
}

function mountCaptions(segments) {
  const root = $('#captions'); root.replaceChildren();
  captions = segments.map((segment, i) => {
    const article = document.createElement('article'); article.className = 'caption';
    const subtitle = document.createElement('p'); subtitle.className = 'eyebrow'; subtitle.textContent = segment.subtitle || '长征 · 翻越雪山';
    const heading = document.createElement(i === 0 ? 'h1' : 'h2'); heading.textContent = segment.title;
    const body = document.createElement('p'); body.className = 'history'; body.textContent = segment.body;
    article.append(subtitle, heading, body); root.append(article);
    return { ...segment, start: clamp(Number(segment.start)), end: clamp(Number(segment.end)), element: article };
  });
}

function updateCaptions() {
  let selected = captions.findIndex((caption) => progress >= caption.start && progress <= caption.end);
  if (selected < 0) selected = Math.min(captions.length - 1, Math.max(0, captions.findIndex((c) => c.start > progress) - 1));
  captions.forEach((caption, i) => {
    const selectedNow = i === selected;
    caption.element.classList.toggle('active', selectedNow);
    caption.element.setAttribute('aria-hidden', String(!selectedNow));
    if (!selectedNow) { caption.element.style.opacity = '0'; return; }
    const local = clamp((progress - caption.start) / Math.max(0.001, caption.end - caption.start));
    const enter = i === 0 ? 1 : smooth(local / 0.23);
    const leave = i === captions.length - 1 ? 1 : 1 - smooth((local - 0.78) / 0.22);
    const opacity = reducedMotion ? 1 : enter * leave;
    caption.element.style.opacity = String(opacity);
    caption.element.style.transform = reducedMotion ? 'none' : `translate3d(${(1 - enter) * 22 - (1 - leave) * 13}px,${(1 - enter) * 18 - (1 - leave) * 14}px,${-(1 - enter) * 130 - (1 - leave) * 170}px) rotateY(${(1 - enter) * 7 - (1 - leave) * 6}deg)`;
  });
  currentCaption = selected;
}

function updateUI(time) {
  updateCaptions();
  if (time - lastUI < 100) return; lastUI = time;
  const percent = Math.round(progress * 100);
  if (document.activeElement !== progressInput) progressInput.value = String(Math.round(progress * 1000));
  progressInput.style.setProperty('--progress', `${progress * 100}%`);
  progressInput.setAttribute('aria-valuetext', `${captions[currentCaption]?.title || '镜头'}，${percent}%`);
  $('#progress-number').textContent = String(percent).padStart(3, '0');
  const buttons = [...document.querySelectorAll('[data-position]')];
  const nearest = buttons.reduce((best, button) => Math.abs(Number(button.dataset.position) - progress) < Math.abs(Number(best.dataset.position) - progress) ? button : best);
  buttons.forEach(button => button.setAttribute('aria-current', String(button === nearest)));
  $('.interaction-hint').style.opacity = progress > 0.08 ? '0' : '.82';
  const desired = Math.round(progress * Math.max(0, urls.length - 1));
  const buffering = ready && !images.has(desired);
  const message = failed.size ? `部分帧装载失败 · 可在制作手记重载` : buffering ? '镜头缓冲中' : ready ? '滚动控制镜头' : '正在装载雪山场景';
  if ($('#frame-status').textContent !== message) $('#frame-status').textContent = message;
  document.documentElement.dataset.progress = progress.toFixed(4);
  document.documentElement.dataset.cached = String(images.size);
}

function loop(time) {
  const dt = Math.min(0.05, Math.max(0, (time - (lastTime || time)) / 1000)); lastTime = time;
  if (tour && ready) {
    tourProgress = clamp(tourProgress + dt / tourDuration);
    window.scrollTo({ top: tourProgress * maxScroll, behavior: 'instant' }); target = tourProgress;
    if (tourProgress >= 1) stopTour();
  }
  progress = reducedMotion ? target : progress + (target - progress) * (1 - Math.exp(-9 * dt));
  if (Math.abs(progress - target) < 0.00003) progress = target;
  demand(progress); drawScene(); drawSnow(time); updateUI(time);
  requestAnimationFrame(loop);
}

async function init() {
  $('#retry').hidden = true; shownError = false;
  try {
    const response = await fetch(manifestURL, { cache: 'no-cache' });
    if (!response.ok) throw new Error(`场景清单未找到 (${response.status})`);
    manifest = await response.json();
    if (!Array.isArray(manifest.frames) || !manifest.frames.length) throw new Error('场景清单中没有渲染帧');
    urls = manifest.frames.map(path => new URL(path, manifestURL).href);
    cacheLimit = innerWidth <= 760 ? 22 : Number(manifest.width) > 1600 ? 28 : 36;
    document.title = `${manifest.title || '雪线之上'} · 长征雪山场景`;
    tourDuration = Math.max(22, Number(manifest.duration) || 36);
    mountCaptions(manifest.segments?.length ? manifest.segments : [
      { start: 0, end: 0.25, title: '雪线之上', subtitle: '1935 · 红军长征', body: '长征途中，红军翻越雪山，在严寒与高山缺氧的艰难环境中继续前进。' },
      { start: 0.25, end: 0.52, title: '走近那面红旗', subtitle: '靠近 · 山间行军', body: '弯曲的行军队伍沿着山脊延伸。风雪中的人影，让遥远的历史逐渐有了尺度。' },
      { start: 0.52, end: 0.78, title: '与队伍同行', subtitle: '同行 · 翻越雪山', body: '从队伍身旁经过，感受地形的陡峭与山路的漫长。此处人物与路径为艺术化概括。' },
      { start: 0.78, end: 1, title: '脚步，还在向前', subtitle: '回望 · 长征记忆', body: '回望雪线，队伍仍向远处延伸。以一段空间记忆，致意长征路上的跋涉。' }
    ]);
    const sourceList = $('#history-sources'); sourceList.replaceChildren();
    for (const source of manifest.historySources || []) {
      const href = new URL(source.url, manifestURL);
      if (!['http:', 'https:'].includes(href.protocol)) continue;
      const li = document.createElement('li'), a = document.createElement('a');
      a.textContent = source.label; a.href = href.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; li.append(a); sourceList.append(li);
    }
    if (!sourceList.children.length) { const li = document.createElement('li'); li.textContent = '史料条目尚待补充；当前为视觉与交互基准样片。'; sourceList.append(li); }
    $('#render-info').textContent = `Blender 渲染序列 · ${manifest.width || '—'} × ${manifest.height || '—'} · ${urls.length} 帧 · ${manifest.fps || '—'} fps`;
    if (manifest.poster) {
      poster = new Image(); poster.onload = () => { renderDirty = true; }; poster.src = new URL(manifest.poster, manifestURL).href;
    }
    failed.clear(); demand(target); $('#loading-message').textContent = '正在装载镜头；滚动可前进，也可回望';
  } catch (error) {
    console.error('[Snow benchmark]', error);
    showError(location.protocol === 'file:' ? '请通过本地服务器打开。运行说明中提供了启动命令。' : `${error.message}。请确认渲染已经完成，再重试。`);
  }
}

addEventListener('scroll', updateScroll, { passive: true });
addEventListener('resize', resize, { passive: true });
addEventListener('wheel', stopTour, { passive: true });
addEventListener('touchstart', stopTour, { passive: true });
addEventListener('keydown', event => {
  if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) stopTour();
  if (event.key === 'Escape' && !$('#production').hidden) toggleProduction(false);
});
progressInput.addEventListener('input', event => seek(Number(event.target.value) / 1000));
document.querySelectorAll('[data-position]').forEach(button => button.addEventListener('click', () => seek(Number(button.dataset.position))));
$('.wordmark').addEventListener('click', event => { event.preventDefault(); seek(0); });
$('#tour').addEventListener('click', () => {
  if (reducedMotion || !ready) return;
  if (tour) { stopTour(); return; }
  if (progress > 0.995) seek(0);
  tourProgress = target; tour = true; $('#tour').setAttribute('aria-pressed', 'true'); $('#tour-label').textContent = '暂停演绎';
});
function toggleProduction(open) {
  $('#production').hidden = !open;
  $('.production-button').setAttribute('aria-expanded', String(open));
  if (open) { stopTour(); $('.close-button').focus(); }
  else $('.production-button').focus();
}
$('.production-button').addEventListener('click', () => toggleProduction($('#production').hidden));
$('.close-button').addEventListener('click', () => toggleProduction(false));
$('#snow-level').addEventListener('input', event => { snowLevel = Number(event.target.value) / 100; $('#snow-value').textContent = `${Math.round(snowLevel * 100)}%`; });
$('#dots-toggle').addEventListener('click', event => {
  dotsEnabled = !dotsEnabled;
  event.currentTarget.setAttribute('aria-pressed', String(dotsEnabled));
  $('#dots-label').textContent = `点描粒子：${dotsEnabled ? '开' : '关'}`;
  if (!dotsEnabled) sky.clearRect(0, 0, width, height);
});
$('#retry').addEventListener('click', () => location.reload());
function applyMotion() {
  reducedMotion = motionQuery.matches;
  $('#tour').disabled = reducedMotion;
  $('#tour').title = reducedMotion ? '已开启减少动态效果，请使用进度条或四个位置按钮浏览' : '沿镜头路径自动前进；滚动或触摸可停止';
  if (reducedMotion) { stopTour(); sky.clearRect(0, 0, width, height); }
}
motionQuery.addEventListener('change', applyMotion);
window.__snowBenchmark = Object.freeze({
  seek,
  getState: () => ({ ready, progress, target, frame: lastFrame, cached: images.size, loaded: seen.size, total: urls.length, pending: pending.size, failed: [...failed], reducedMotion, tour, manifest: manifestURL.href, hasError: shownError })
});
resize(); applyMotion(); init(); requestAnimationFrame(loop);
