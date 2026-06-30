# Demo Assets

README 首页需要稳定展示效果，但完整视频不应该拖慢 clone 或源码下载。

当前方案：

- `docs/demo/wtf-loop-engineer-preview.gif`：保留在仓库里，约 490KB，用于 README 首页直接展示动态预览。
- 完整 5 分钟 MP4：托管在 GitHub Release asset，不进入仓库当前文件树。
- Release 链接：<https://github.com/nateEc/yt-dub-studio/releases/download/demo-v1/wtf-loop-engineer-first5-sourcevoice-wav2lip.mp4>

取舍：

- GitHub Release asset：适合大 demo 文件；可版本化、可替换、可直接链接，不增加当前源码下载体积。
- Git LFS：不采用。它会引入 LFS 客户端和配额/带宽问题，对普通 clone 用户不够透明。
- GitHub user-attachments：不采用。它适合临时 README/issue 媒体展示，但上传、替换和归档管理不如 Release asset 清楚。
- `docs/demo`：只存轻量预览/封面，不再存完整 MP4。

注意：GitHub README 会过滤仓库内的 `<video>` HTML 标签，因此首页使用 GIF 预览 + Release MP4 链接的组合。
