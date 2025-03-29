# zhenxun_plugin_zhipu_toolkit
智谱AI全家桶，省时省力省心

一次安装，多种功能

> [!IMPORTANT]
> 插件需要智谱AI的API KEY，请安装插件后在`data/config.yaml`中配置，保存文件后插件会自动重载
>
> 插件默认使用平台的免费模型，只需注册即可，无任何花费

> [!NOTE]
> **关于模型选择**
>
> 若经济实力支持，建议使用对话模型`GLM-4-Air`(0.0005CNY/k tokens)以取得更好的效果
>
> 部分模型不支持调用工具，尽量不要使用(比如`CharGLM-4`, 向量/代码模型系列等)



## 🔑 获取智谱AI的token

前往[https://bigmodel.cn/login](https://bigmodel.cn/login)手机号注册/登录，注册后不需要实名

注册/登录后，访问[此链接](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)即可看到你的`API KEY`,复制后填写即可

**温馨提示:** 把鼠标移至TOKEN上，会出现复制按钮，点击即可
![image](https://github.com/user-attachments/assets/949de9e7-07c8-4451-9d22-a0fd3d5190a9)

## 📚 插件依赖
如果插件报错没有加载，说明真寻自动安装依赖失败了，请在Bot目录执行以下命令
```shell
poetry add zhipuai
```

## ✨ 功能
- [x] AI文生图
- [x] AI文生视频
- [x] AI上下文对话
- [x] 用户分组上下文
- [x] 支持多模态
- [x] 伪人模式
- [x] 调用工具
- [x] 图像理解
- [x] 网页总结

## TODO
- [ ] 添加更多工具

## 🚀 安装
对 Bot 发送`添加插件 zhipu_toolkit`即可安装

## ⚠️ 注意事项
1. 本插件已包含真寻AI插件默认的`hello`功能，使用本插件前请先**卸载**真寻的AI插件
2. 请删除`zhenxun/builtin_plugins/nickname.py`这个插件，**否则可能会与本插件冲突**

## 🎉 使用
| 命令 | 参数 | 范围 | 说明 |
|:---:|:---:|:---:|:---:|
| `生成图片` | `(可选)size` `prompt` | 私聊/群聊 | 根据给出文本生成图片,如果没有传入会询问用户 |
| `生成视频` | `(可选)生成内容基于的图片` `prompt` | 私聊/群聊 | 根据给出文本或图片生成视频,如果没有传入会询问用户 |
| `-` | `prompt` | 私聊/群聊 | 上下文对话，需要@Bot或叫Bot的名字 |
| `清理我的会话` | -  | 私聊/群聊 | 用于清理你与AI的聊天记录 |
| (ADMIN)`清理群会话` | - | 群聊 | 用于清理本群会话，仅当分组模式为group时生效，需要管理员权限 |
| (SUPERADMIN)`清理全部会话` | - | 私聊/群聊 | 清理Bot缓存的全部会话记录 |
| (SUPERADMIN)`清理会话` | `@user / uid` | 私聊/群聊 | 用于清理指定用户的会话记录,支持多个目标 |
| (ADMIN)`启用/禁用伪人模式` | - | 群聊 | 开启或关闭当前群聊的伪人模式|
| (SUPERADMIN)`启用/禁用伪人模式` | `group_id` | 私聊/群聊 | 开启或关闭指定群聊的伪人模式|

## ⚙️ 配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| `API_KEY` | **是** | `None` | 智谱ai的API KEY |
| `CHAT_MODEL` | **否** | `glm-4-flash`| 所使用的对话模型代码 |
| `PIC_MODEL` | **否** | `cogview-3-flash` | 所使用的图片生成模型代码 |
| `VIDEO_MODEL` | **否** | `cogvideox-flash` | 所使用的视频生成模型代码|
| `IMAGE_UNDERSTANDING_MODEL` | **否** | `glm-4v-flash` | 所使用的图片理解模型代码 |
| `CHAT_MODE` | **否** | `user` | 对话分组模式，支持'user','group','all' |
| `SOUL` | **否** | `你是真寻，你强大且无所不能` | AI的自定义人格 |
| `IMPERSONATION_MODE` | **否** | `False` | 是否启用伪人模式 |
| `IMPERSONATION_TRIGGER_FREQUENCY` | **否** | `20` | 伪人模式触发频率[0-100] |
| `IMPERSONATION_MODEL` | **否** | `glm-4-flash` | 伪人模式对话模型,由于对话量大，建议使用免费模型 |
| `IMPERSONATION_SOUL` | **否** | `False` | 伪人模式的自定义人格,为`False`则同步`SOUL` |
| `IMPERSONATION_BAN_GROUP` | **否** | `[]` | 禁用伪人模式的群组列表 |

## ⁉️ Q&A
- **Q:** 什么是伪人模式
- 开启此模式后，bot会如同真人一般，读取最近20条群友的聊天记录，然后根据这些内容进行发言。此模式默认触发概率为20%，可以通过配置`IMPERSONATION_TRIGGER_FREQUENCY`进行修改.