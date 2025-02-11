# zhenxun_plugin_zhipu_toolkit
智谱AI全家桶，省时省力省心

一次安装，多种功能

> [!IMPORTANT]
> 插件需要智谱AI的API KEY，请先在插件配置中设置
>
> 插件使用平台的免费模型，只需注册即可，无任何花费


## 🔑 获取智谱AI的token

前往[https://bigmodel.cn/login](https://bigmodel.cn/login)手机号注册/登录，注册后不需要实名

注册/登录后，访问[此链接](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)即可看到你的`API KEY`,复制后填写即可

**温馨提示:** 把鼠标移至TOKEN上，会出现复制按钮，点击即可
![image](https://github.com/user-attachments/assets/949de9e7-07c8-4451-9d22-a0fd3d5190a9)

## ✨ 功能
- [x] AI文生图
- [x] AI文生视频
- [x] AI上下文对话
- [x] 用户分组上下文
- [x] 支持多模态
- [x] 伪人模式

## TODO
- [ ] 支持联网搜索

## 🚀 安装
对 Bot 发送`添加插件 zhipu_toolkit`即可安装

## ⚠️ 注意事项
1. 本插件已包含真寻AI插件默认的`hello`功能，使用本插件前请先**卸载**真寻的AI插件
2. 请删除`zhenxun/builtin_plugins/nickname.py`这个插件，**否则可能会与本插件冲突**

## 🎉 使用
| 命令 | 参数 | 范围 | 说明 |
|:---:|:---:|:---:|:---:|
| `生成图片` | `prompt` | 私聊/群聊 | 根据给出文本生成图片,如果没有传入会询问用户 |
| `生成视频` | `prompt` | 私聊/群聊 | 根据给出文本生成视频,如果没有传入会询问用户 |
| `-` | `prompt` | 私聊/群聊 | 上下文对话，需要@Bot或叫Bot的名字 |
| `清理我的会话` | -  | 私聊/群聊 | 用于清理你与AI的聊天记录 |
| `清理群会话` | - | 群聊 | 用于清理本群会话，仅当分组模式为group时生效，需要管理员权限 |
| `清理全部会话` | - | 私聊/群聊 | 清理Bot缓存的全部会话记录 |

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
| `IMPERSONATION_SOUL` | **否** | `False` | 伪人模式的自定义人格,为False则同步SOUL |

## 📚 插件依赖
如果插件报错了没有加载，说明真寻自动安装依赖失败了，请在Bot目录执行以下命令
```shell
poetry add zhipuai
```

## ⁉️ Q&A
- **Q:** 什么是伪人模式
- 开启此模式后，bot会如同真人一般，读取最近20条群友的聊天记录，然后根据这些内容进行发言。此模式默认触发概率为20%，可以通过配置`IMPERSONATION_TRIGGER_FREQUENCY`进行修改.