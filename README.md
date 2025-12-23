# Yt-dlp GUI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-6.9.0+-green.svg)
![yt-dlp](https://img.shields.io/badge/yt--dlp-2025.12.8+-red.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

**一个基于 PySide6 和 yt-dlp 开发的现代化视频下载工具**

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [常见问题](#-常见问题) 

</div>

---

## 📖 项目简介

**Yt-dlp GUI** 是一款轻量级、现代化的跨平台视频下载工具，基于强大的 `yt-dlp` 内核和优雅的 `PySide6` 框架构建。它为用户提供了直观友好的图形界面，让下载来自 YouTube、Bilibili、Vimeo 等数千个视频网站的内容变得简单高效。

### 🎯 核心优势

- **🚀 高性能**：采用多线程架构，下载任务在后台运行，界面始终保持流畅响应
- **🎨 现代化设计**：精心设计的深色主题界面，提供舒适的视觉体验
- **🔧 高度可配置**：丰富的格式预设和自定义选项，满足不同场景需求
- **🛡️ 稳定可靠**：完善的错误处理和重试机制，确保下载任务顺利完成
- **🌐 网络友好**：内置代理支持，轻松应对网络访问限制

## ✨ 功能特性

### 🎬 下载功能
-   **多平台支持**：基于强大的 `yt-dlp` 内核，支持 YouTube、Bilibili、Vimeo、Twitter 等数千个视频网站
-   **智能格式选择**：内置多种下载格式预设，包括最佳质量、4K、1080p、720p 视频及仅音频下载
-   **自动音视频合并**：自动下载最佳视频和音频流，并使用 FFmpeg 合并为 MP4 格式
-   **断点续传支持**：支持下载中断后继续，节省时间和带宽

### 📊 进度与状态
-   **实时进度显示**：详细的下载进度条，精确显示下载百分比
-   **速度监控**：实时显示下载速度，了解当前网络状况
-   **剩余时间预测**：智能计算并显示预计剩余时间
-   **详细日志输出**：完整的下载日志记录，方便排查问题和追踪下载状态

### ⚙️ 高级功能
-   **代理支持**：内置 HTTP/SOCKS 代理配置，轻松应对网络访问限制
-   **多线程架构**：下载任务在独立后台线程运行，界面始终保持流畅响应
-   **任务取消**：下载过程中可随时取消，优雅退出
-   **自定义保存路径**：灵活选择文件保存目录，默认使用系统下载文件夹
-   **错误重试机制**：内置自动重试功能（最多 10 次），提高下载成功率

## 📸 界面预览

<div align="center">

![主界面](./screenshot.png)

*深色主题主界面，简洁直观的下载体验*

</div>

---

## 🚀 快速开始

### 环境要求

-   Python 3.12 或更高版本
-   uv (推荐的包管理器)
-   FFmpeg (用于音视频合并，建议安装并添加到系统环境变量)

### 安装步骤

1.  **克隆仓库**
    ```bash
    git clone https://github.com/twn39/yt-dlp-gui.git
    cd yt-dlp-gui
    ```

2.  **安装依赖**
    推荐使用 `uv` 安装：
    ```bash
    uv sync
    ```

3.  **运行程序**
    
    有多种启动方式：
    
    **方式一：使用命令行工具（推荐）**
    ```bash
    uv run yt-dlp-qt-gui
    ```
    
    
    查看版本信息：
    ```bash
    uv run yt-dlp-qt-gui --version
    ```
    
    查看帮助信息：
    ```bash
    uv run yt-dlp-qt-gui --help
    ```

---

## 🛠️ 技术栈

## 📦 打包为可执行文件

### 安装打包依赖

```bash
uv sync --extra packaging
```

### 执行打包

```bash
# 使用打包脚本（推荐）
uv run python build.py

# 或直接使用 PyInstaller
uv run pyinstaller --clean yt-dlp-qt-gui.spec
```

打包完成后，可执行文件位于 `dist/` 目录中。

### 跨平台打包

- **Windows**: 在 Windows 系统上打包，生成 `.exe` 文件
- **macOS**: 在 macOS 系统上打包，生成可执行文件
- **Linux**: 在 Linux 系统上打包，生成可执行文件

### 注意事项

- 打包后的应用仍需要系统安装 FFmpeg
- macOS 用户可能需要在系统设置中允许运行未签名的应用
- 首次运行可能需要防火墙权限

## 🛠️ 技术栈

-   **GUI 框架**: [PySide6](https://doc.qt.io/qtforpython/) (Qt for Python)
-   **下载引擎**: [yt-dlp](https://github.com/yt-dlp/yt-dlp)
-   **图标库**: [QtAwesome](https://github.com/Spyder-IDE/qtawesome)
-   **命令行工具**: [Click](https://click.palletsprojects.com/)
-   **打包工具**: [PyInstaller](https://www.pyinstaller.org/)
-   **包管理器**: [uv](https://github.com/astral-sh/uv)


## 📝 常见问题

### Q: 下载失败怎么办？

A: 请检查以下几点：
-   确认 URL 是否正确且可访问
-   检查网络连接是否正常
-   尝试使用代理解决网络限制
-   查看日志输出了解具体错误信息

### Q: FFmpeg 是必须的吗？

A: 是的。FFmpeg 用于音视频合并，建议安装并添加到系统环境变量中。如果未安装，某些视频格式可能无法正常下载。

### Q: 支持哪些视频网站？

A: 本项目基于 `yt-dlp`，支持数千个视频网站，包括但不限于：
-   YouTube
-   Bilibili
-   Vimeo
-   Twitter/X
-   Instagram
-   TikTok
-   以及更多...

完整支持列表请参考 [yt-dlp 官方文档](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出改进建议！

### 如何贡献

1.  Fork 本仓库
2.  创建特性分支 (`git checkout -b feature/AmazingFeature`)
3.  提交更改 (`git commit -m 'Add some AmazingFeature'`)
4.  推送到分支 (`git push origin feature/AmazingFeature`)
5.  开启 Pull Request

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/twn39/yt-dlp-gui.git
cd yt-dlp-gui

# 使用 uv 安装依赖（推荐）
uv sync

# 运行程序
uv run yt-dlp-qt-gui
```

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

本项目基于以下优秀的开源项目：

-   [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 强大的视频下载工具
-   [PySide6](https://doc.qt.io/qtforpython/) - Qt for Python GUI 框架
-   [QtAwesome](https://github.com/Spyder-IDE/qtawesome) - FontAwesome 图标库
-   [FFmpeg](https://ffmpeg.org/) - 多媒体处理框架

感谢所有为这些项目做出贡献的开发者！

---

## 📮 联系方式

如有问题或建议，欢迎通过以下方式联系：

-   提交 [Issue](https://github.com/your-username/yt-dlp-gui/issues)
-   发起 [Pull Request](https://github.com/your-username/yt-dlp-gui/pulls)

