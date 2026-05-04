---
triggers: ["发布", "推送", "上线", "publish", "deploy"]
tools: ["git_status", "git_current_sha", "git_commit_push", "hexo_deploy"]
---

# 发布技能

当用户要求把改动推送到 GitHub Pages 时，启用以下流程。

## 发布前检查清单
1. 调用 git_status 列出本次改动
2. 列出本次新增/修改了哪些文章
3. 生成简洁的 commit message：
   - 新增单篇：`新增文章：<标题>`
   - 新增多篇：`新增 N 篇文章`
   - 仅修改：`修订：<文章标题>`

## 完整发布流程
一次完整的发布需要两步：
1. `git_commit_push` —— 推送源码到 GitHub（保留版本历史）
2. `hexo_deploy` —— 编译为 HTML 并部署到 Pages（让网页真正更新）

两步都需要用户审批。第一步成功后再执行第二步。
如果用户只说"发布"，应理解为完整执行这两步。

## 必须的人工确认环节
**在调用 git_commit_push 前**，先向用户报告：
- 本次将要推送的文件清单
- commit message 草稿
- 预计的部署效果

等待用户回复"确认/发布/推送/y"之后再调用 git_commit_push。
审批门会再次拦截一次（双保险）。

## 失败处理
- push 被拒（非 fast-forward）：先 git pull --rebase 再重试
- 网络错误：提示用户检查 SSH 配置
- 任何不确定的失败：停止并向用户求助，不要自行重试 git_reset
