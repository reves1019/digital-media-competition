# 雪山雕塑 · 实时 GLB 查看器

这是单体雕塑的白膜与粒子第一阶段验收页。它读取真实 Blender 导出的 `snow_mountain_sculpture.glb`，在浏览器中以高粗糙度哑光石膏实时渲染；彩色粒子来自 Blender 固定索引的 512×512 morph 缓存，浏览器用 GPU FBO 插值五个目标，白膜始终作为主体可见。

## 资源位置

把文件放到：

```text
snow-benchmark/assets/snow_mountain_sculpture.glb
snow-benchmark/assets/snow_mountain_morph_points_512.bin
```

查看器通过 `../assets/snow_mountain_sculpture.glb` 读取。GLTFLoader 会随 GLB 读取同目录下的外部纹理或二进制依赖；本阶段建议导出自包含 GLB，避免贴图路径漂移。

## 启动

从比赛项目根目录启动静态服务器：

```powershell
py -3 -m http.server 4173 --bind 127.0.0.1
```

然后打开 `/snow-benchmark/sculpture-viewer/`。不要直接双击 HTML，浏览器会阻止模块和 GLB 的本地读取。

## 交互

- 默认“滚动运镜”：页面高度 400vh，固定 Three.js 画布。滚轮控制一条 CatmullRom 相机路径，可向上回望。
- 四个镜头位置对应总览、中段人物、高脊、回望（0、0.333、0.667、1）；位置与目标点已按 Blender y-up 坐标写入 `app.js`。
- “自由查看”才启用 OrbitControls，可拖拽旋转与滚轮缩放；滚动模式不会抢占页面滚轮。
- “彩色粒子”固定为 262,144 个纹理索引，默认开启、28% 强度；二进制中的 `rock / figure / flag` role mask 控制灰白主体与殷红旗帜的亮度和点径，保留整件雕塑的粒子体积，不再只绘制一圈轮廓。颜色、phase 和角色来自 `snow_mountain_morph_points_512.bin`，点大小约 1.35—7.2 px，默认透明度受滑块限制。
- 粒子模拟使用两个 512×512 `RGBA32F` `WebGLRenderTarget` ping-pong。全屏 simulation shader 根据滚动进度在 `surface → breathing → ridgeCloud → disperse → return` 五个目标之间插值，再由 point shader 采样当前 position texture；0—1 滚动进度对应完整 A→E 过程。Blender 的 Z-up 坐标在上传时转换为 GLTFLoader 的 Y-up `(x, z, -y)`。
- point shader 用 `gl_PointCoord` 圆形 discard 做软遮罩，关闭深度测试、关闭深度写入，避免模型前后表面吞掉粒子；白膜主体不会被粒子层替换。
- “白膜 · 开/隐藏”可直接比较实体雕塑与 GPU 粒子主体；默认保留白膜以保证人物和岩层在评审截图中可读。
- “表面点云”从模型三角面确定性采样，最多 50,000 个点，默认关闭；打开时作为单独的低透明度轮廓验收视图，便于检查模型粒子化方向，不添加漂浮风雪。
- 制作说明中的强度滑块可将彩色粒子降到 0；粒子开关只影响彩色粒子层。系统开启“减少动态效果”时取消时间驱动的流动与呼吸，仍可随滚动查看静态阶段。
- “制作说明”展示真实加载状态、网格数量、三角面数和模型尺寸。缺失或损坏 GLB 会给出重试入口。
- 系统开启“减少动态效果”时，滚动相机不做额外平滑，自由查看关闭阻尼。

## 本地依赖

`vendor/build/three.module.js`、`vendor/build/three.core.js`、`vendor/examples/jsm/loaders/GLTFLoader.js`、`vendor/examples/jsm/controls/OrbitControls.js` 与 `vendor/examples/jsm/utils/BufferGeometryUtils.js` 固定来自 three.js `0.180.0`，已经把浏览器裸模块导入改为本地相对路径；页面运行时不请求 CDN。Three.js 许可证随发行包位于上游仓库，版本与来源记录在此 README；`vendor/LICENSE-threejs.txt` 保留 MIT 许可说明。

## 检查接口

控制台提供 `window.__sculptureViewer.getState()` 和 `.setProgress(0..1)`，可验证模型、morph 资产、FBO 能力、网格/三角面/尺寸、当前相机模式、彩色粒子点数、表面点云点数与当前强度。`node --check app.js` 与三个本地加载器模块应全部通过。部分旧浏览器无法写入浮点 FBO 时，粒子状态会保持禁用并在控制台报告原因。

当前 `snow_mountain_sculpture.glb` 已用 Blender 5.2 后台导入验证通过；查看器本身的 Three.js 模块也已在 Node 中完成本地 ESM 导入检查。浏览器/WebGL 视觉验收应在正式静态服务器上进行。
