# 应用工程基线

这里保留来自 FastAPI 官方全栈模板的前后端应用源码与锁文件，并加入本项目的隔离 G0 验证配置。它包含登录、用户及示例 Item 等模板功能，**尚未实现本项目售后会话、验效内核和客服工作台**。

原许可证见 [LICENSE](LICENSE)，来源见 [REUSE_MANIFEST.json](REUSE_MANIFEST.json) 和 [根目录第三方声明](../THIRD_PARTY_NOTICES.md)。公开版本没有导入上游 Git 历史或本机 `.env`，也不包含上游自动部署工作流。

## 最小复现条件

- Docker 的 Linux 容器引擎及 Compose。
- Windows PowerShell 或 PowerShell 7，用于运行本目录脚本。
- 拉取公开容器镜像和锁定依赖的网络连接。
- 基线后端依照 `pyproject.toml` 要求 Python 3.14；隔离验证镜像已指定依赖与镜像摘要。前端沿用 Bun 锁文件。

进入本目录后执行：

```powershell
powershell -NoProfile -File scripts/initialize-g0.ps1
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Build
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Database
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Tests
```

PowerShell 7 环境可将命令中的 `powershell` 替换为 `pwsh`。公开版脚本直接调用 Docker，不要求安装本机开发使用的命令包装工具。

初始化脚本仅在 `.env.g0` 不存在时生成随机本地口令，不打印口令、不覆盖已有配置。测试只允许写入专用 `yibu_g0_test` 数据库。配置不发布宿主机端口、不挂载 Docker socket，不对外开放演示页面。运行测试需要的邮件发送使用显式替身，并不验证真实送达。

## 持久性和静态检查

```powershell
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Write
powershell -NoProfile -File scripts/run-g0.ps1 -Phase RestartDatabase
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Database
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Read
powershell -NoProfile -File scripts/run-g0.ps1 -Phase Lint
```

先完成 Tests 再进行 Write/RestartDatabase/Read。再次执行 Tests 可能清理测试用户与示例 Item，因此旧持久性结果不能自动延续。测试记录生成于本机 `evidence/g0/`，默认不提交。

完成后可停止数据库且保留数据卷：

```powershell
docker compose --env-file .env.g0 -f compose.g0.yml stop db
```

不要替换为真实业务数据库。这里不提供删除数据卷或公网部署的自动命令。

## 验证口径

2026-09-22 本地历史记录曾显示 58 项上游后端测试通过；本次公开发布不等于重新完成该套 Docker 测试。历史原始日志和本地凭据均未公开，请按上述入口自行复现。

原开发目录中的 `audit-g0.ps1` 会检查上游远端与原提交，因此不适用于这个重新组织的发布仓库，没有直接复制。导出文件的原始与公开 SHA-256 记录于 [SOURCE_MANIFEST.json](../SOURCE_MANIFEST.json)。
