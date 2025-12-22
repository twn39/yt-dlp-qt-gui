# Yt-dlp GUI

一个基于 **PySide6** 和 **yt-dlp** 开发的轻量级、现代化的视频下载工具。它提供了直观的图形用户界面，让您可以轻松下载来自各大视频网站的内容。

## ✨ 功能特性

-   **多平台支持**：基于强大的 `yt-dlp` 内核，支持数千个视频网站。
-   **直观界面**：采用 PySide6 构建的现代化深色主题界面。
-   **格式预设**：内置多种下载格式选项，包括 4K/1080p/720p 视频及仅音频下载。
-   **拖拽支持**：支持直接将视频 URL 拖拽到窗口中进行下载。
-   **实时进度**：详细的下载进度条、速度显示及剩余时间预测。
-   **代理设置**：内置 HTTP/SOCKS 代理支持，解决网络访问限制。
-   **多线程下载**：下载任务在后台线程运行，界面流畅不卡顿。
-   **日志记录**：完整的下载日志输出，方便排查问题。

## 🚀 快速开始

### 环境要求

-   Python 3.12 或更高版本
-   FFmpeg (用于音视频合并，建议安装并添加到系统环境变量)

### 安装步骤

1.  **克隆仓库**
    ```bash
    git clone https://github.com/your-username/yt-dlp-gui.git
    cd yt-dlp-gui
    ```

2.  **安装依赖**
    推荐使用 `uv` 或 `pip` 安装：
    ```bash
    pip install -r requirements.txt
    # 或者使用 uv
    uv sync
    ```

3.  **运行程序**
    ```bash
    python main.py
    ```

## 🛠️ 技术栈

-   **GUI 框架**: [PySide6](https://doc.qt.io/qtforpython/) (Qt for Python)
-   **下载引擎**: [yt-dlp](https://github.com/yt-dlp/yt-dlp)
-   **图标库**: [QtAwesome](https://github.com/Spyder-IDE/qtawesome)
-   **样式**: 自定义 QSS 深色主题

## 📂 项目结构

-   [`main.py`](main.py): 程序入口，负责 UI 布局和交互逻辑。
-   [`worker.py`](worker.py): 核心下载逻辑，封装了 `yt-dlp` 的异步调用。
-   [`config.py`](config.py): 集中管理下载格式、UI 颜色和默认设置。
-   [`dark_theme.qss`](dark_theme.qss): 界面样式定义。

## ⚙️ 配置说明

您可以在 [`config.py`](config.py) 中修改以下设置：
-   `DEFAULT_FORMAT`: 默认下载质量。
-   `FORMAT_PRESETS`: 下拉菜单中的格式选项。
-   `WINDOW_TITLE`: 窗口标题。
-   `PROXY`: 默认代理配置。

## 📝 使用提示

-   **粘贴 URL**: 点击工具栏的“粘贴”图标或使用 `Ctrl+V`。
-   **保存目录**: 默认保存至系统的“下载”文件夹，可通过“浏览”按钮更改。
-   **取消下载**: 下载过程中可随时点击“取消”按钮中断任务。

## ⚖️ 许可证

本项目仅供学习和研究使用，请遵守当地法律法规及目标网站的服务条款。