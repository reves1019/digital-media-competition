# 雪山镜头网页

从项目根目录启动静态服务器，然后打开 `/snow-benchmark/web/`。不要双击 HTML：浏览器会拦截本地 JSON 读取。

```powershell
py -3 -m http.server 4173 --bind 127.0.0.1
```

画面是 Blender 三维场景的预渲染帧序列。滚轮控制既定镜头路径的进度，支持倒放；浏览器绘制少量前景雪点与有透视变化的文字。不是实时自由视角三维渲染，鼠标不会改变 Blender 相机路径。

制作手记中的“前景雪点”控制浏览器侧气氛叠加。默认打开“点描粒子”，浏览器从当前渲染帧的小尺寸亮度、边缘和红色信号采样稀疏点光，模拟参考图中的颗粒记忆层；这是屏幕空间叠加，不是伪装成 Blender 粒子的实时三维系统。它保持约 70% 的完整 Blender 画面与少量雪点/光尘，也可以手动关闭来检查纯渲染构图。

## 资源契约

读取 `../assets/manifest.json`，所有帧与 poster 地址**以 manifest.json 为基准解析**。推荐格式：

```json
{
  "title": "雪线之上",
  "fps": 12,
  "frameCount": 120,
  "width": 1280,
  "height": 720,
  "duration": 30,
  "frames": ["frames/frame_0001.webp", "frames/frame_0002.webp"],
  "poster": "poster.jpg",
  "segments": [
    {"start": 0, "end": 0.25, "title": "雪线之上", "subtitle": "1935 · 红军长征", "body": "经核对后的历史文字"},
    {"start": 0.25, "end": 0.52, "title": "走近那面红旗", "subtitle": "靠近", "body": "..."},
    {"start": 0.52, "end": 0.78, "title": "与队伍同行", "subtitle": "同行", "body": "..."},
    {"start": 0.78, "end": 1, "title": "脚步，还在向前", "subtitle": "回望", "body": "..."}
  ],
  "historySources": [{"label": "资料名称", "url": "https://example.org/source"}]
}
```

`frames.length` 是实际序列长度，start/end 是 0—1 的归一化镜头区间。duration 是自动演绎时长（秒），至少 22 秒。当前四个镜头位置分别为 0、0.32、0.64、1；可按成片微调 HTML 中 data-position。

## 手感与性能

- 页面高度 640vh、原生滚动，视觉进度仅使用一次 `1 - exp(-9 * dt)` 平滑，不拦截滚轮。
- 附近 24 帧优先缓存，4 并发读取；大于缓存上限时移除离当前镜头最远的帧，跳转立即提高目的帧优先级。
- 桌面常驻 36 帧；宽度超过 1600 的序列常驻 28 帧；移动端 22 帧。旧画面在缓冲期间保持显示。
- 相邻帧短暂交叉混合可以减轻低帧率阶梯感；这是帧混合，不是生成新的三维中间帧。复杂运动的鬼影需通过提高源帧率解决。
- 窄屏采用完整画面置入，避免裁掉队列。桌面仅在裁切比例小于约 12% 时铺满。
- 系统减少动态效果时，取消镜头平滑、雪点与自动演绎，仍可用进度条/位置按钮选帧。
- 页面不请求外网；字体使用原项目的 `assets/outfit-regular.ttf`，缺失时使用系统字体。史料链接仅在点击后打开。

## 核验

提供 `window.__snowBenchmark.getState()` 与 `.seek(0..1)`，便于检查装载失败、当前帧、缓存数量和归一化进度。`document.documentElement.dataset` 同时公开 progress/frame/cached。制作手记准确说明预渲染与浏览器叠加的边界。

发布前应在实际帧资源完成后验证：首帧、四个节点、倒滚、快速跳转、进度滑块、自动演绎中断、减少动态效果、移动端完整构图、史料链接与装载失败重试。
