# 翻雪山雕塑基准场景

这一版按用户提供的雕塑照片和 `7d1e9dcb2548545264f9e15d831bc593.mp4` 的近景重新制作。场景主体是一件 `SCULPTURE_ROOT`：斜向抬升的雪山岩体、断层片、支撑根部，以及嵌在岩脊上的 14 个原创人物姿态。人物使用攀爬、牵引、跪伏、匍匐、搀扶和站立等雕塑化姿态，和岩体属于同一件模型；没有复制视频字幕、水印、现代徽章或红旗。

这是依据单视图和视频接触帧完成的原创低中模重建，不是博物馆原件扫描。照片看不到的背面、底面和内部空腔由结构推断补建。

## 文件

- `blender/build_sculpture.py`：场景、材质、人物群、灯光和镜头路径的可重复构建脚本。
- `blender/sculpted_figures.py`：人物姿态与衣褶/背包/杆件模块。
- `blender/snow_mountain_sculpture.blend`：可继续编辑的 Blender 工程。
- `assets/snow_mountain_sculpture.glb`：仅导出雕塑集合，可给网页实时查看器使用。
- `assets/sculpture-camera-path.json`：240 帧镜头路径。
- `renders/sculpture_overview.png`：基准定妆帧；`sculpture_figures.png` 和 `sculpture_high_ridge.png` 是近景验证图。
- `blender/build_particle_sculpture.py`：从白膜工程表面采样并生成灰白粒子场、殷红粒子旗帜的可重复脚本。
- `blender/snow_mountain_particle_sculpture.blend`：粒子版可编辑 Blender 工程，原白膜集合保留但默认不参与粒子版渲染。
- `renders/particle_sculpture_overview.png`、`renders/particle_sculpture_close.png`：粒子版总览与近景。
- `blender/build_morph_particle_sculpture.py`：按 morph-particles 思路生成固定索引的高密度粒子目标。
- `blender/snow_mountain_morph_particles_512.blend`：512×512 固定点粒子场的可编辑工程。
- `assets/snow_mountain_morph_points_512.bin`：五个形态目标、颜色、相位和角色标记；网页端可直接上传到 RGBA32F/FBO。
- `assets/snow_mountain_morph_normals_512.bin`：与固定点一一对应的归一化法线，供网页端粒子光照或轮廓增强使用。
- `assets/snow_mountain_morph_manifest.json`：点数、字段偏移、端序和角色值的机器可读清单。
- `renders/morph_particle_sculpture_512.png`：262,144 点版本的静态验收图。

当前输出是白膜验收版：偏暖白的高粗糙度哑光石膏材质，主岩体约 4.8 万顶点，人物和层理合计约 11.3 万顶点；暗部保留给后续粒子和文字叠加，避免白色表面过曝。

粒子版使用 52,000 个灰白表面粒子和 744 个殷红旗帜粒子，白色粒子约 37,375 个、烟灰粒子约 14,625 个。粒子通过 Geometry Nodes 实例化低面数球体，保留岩体与人物的整体轮廓；两面红旗单独生成，避免红色随机污染主体。粒子版当前重点是静态构成与材质验收，原工程相机仍保留 240 帧路径，后续可继续接入滚动聚散动画。

高密度 morph 版固定为 262,144 个点（512×512），其中 261,400 个采样自岩体和人物表面，744 个属于两面旗帜。每个点在五个目标中保持同一索引：`surface`、`breathing`、`ridgeCloud`、`disperse`、`return`。Blender 负责高精度表面采样、法线、颜色和角色标记；网页端再用 GPU FBO 根据滚轮进度插值这些目标。

## 重建与验证

```powershell
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_sculpture.py' -- --model-only
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_sculpture.py' -- --preview
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_sculpture.py' -- --views
# 如需回看上一版深灰泥塑：
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_sculpture.py' -- --preview --grey
# 生成灰白粒子版与殷红旗帜
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_particle_sculpture.py'
# 生成 512×512 fixed-index morph 粒子数据、Blender 工程和验收图
& 'D:\Blender\blender.exe' --background --factory-startup --python 'snow-benchmark/blender/build_morph_particle_sculpture.py'
```

Blender 5.2 LTS 已用本机 RTX 5060 Laptop GPU 的 OptiX 路径验证；WebGL 查看器现在读取同一份 512×512 fixed-index morph 数据，用两个 RGBA32F FBO 在浏览器 GPU 中按滚轮插值五个目标。白膜保留为可读性底层，彩色粒子层是真实位置纹理驱动的 262,144 点，不是预渲染视频或屏幕空间假粒子。

历史字幕仅引用夹金山资料，见网页中的来源列表；正式参赛前仍要由作者复核史实文字、展品版权和视频引用范围。
