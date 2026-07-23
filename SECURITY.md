# 安全说明

## 适用范围

本仓库仅用于集成演示。请勿将本地 Token 签发接口、默认 Secret 或内存客户端视为生产安全控制。

保持默认服务仅绑定 Loopback 地址。不要将默认配置暴露到不可信网络。

## 部署检查清单

部署前完成以下操作：

- 将 `/demo-token` 替换为可信身份提供商；
- 对每个请求验证 Issuer、Audience、签名、过期时间和 Subject；
- 从可信服务端数据源重建 Tenant、Role、数据范围和 Tool 权限；
- 将所有 Thread 和延续操作绑定到已认证 Owner；
- 在读取或修改数据前授权每一次 Tool 调用；
- 添加请求频率、并发数、请求体大小、执行时间和输出限制；
- 启用 HTTPS，并将 CORS 限制为准确的 Origin；
- 记录审计事件，但不要记录原始 Token 或敏感内容；
- 将内部异常映射为通用外部错误；
- 尽可能将 Agent 接口置于可信 BFF 或 API Gateway 之后；
- 检查依赖安全公告和适用的产品许可证；
- 在生产环境使用 `selfManagedAgents` 前确认 Enterprise Intelligence 许可和费用。

不要提交 `.env` 文件、Access Token、Private Key、私密 License Token、用户数据或包含敏感信息的生成 Trace。

## 漏洞报告

在接受外部用户之前，请在仓库设置中启用私有漏洞报告。项目建立维护团队后，发布安全联系人和响应流程。
