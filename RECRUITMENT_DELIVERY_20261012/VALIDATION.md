# 交付检查

- 前端 npm run build 成功。
- 375 个 Python 文件语法解析通过。
- 无 node_modules、虚拟环境、.runtime、真实 .env 与 private 数据文件。
- 保留已构建的前端静态文件。
- 交付副本 BOSS-cli --help 与 Boss-main main.py --help 通过（借用原项目依赖环境，不代表异机安装通过）。BOSS-cli 使用启动脚本已设置的 PYTHONUTF8=1，避免 Windows GBK 输出错误。
- 未执行真实发送，也未完成异机全新依赖安装测试。
