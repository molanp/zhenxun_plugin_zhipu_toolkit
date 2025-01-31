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

## TODO
- [ ] 支持多模态
- [ ] 支持联网搜索

## 🚀 安装
对 Bot 发送`添加插件 zhipu_toolkit`即可安装

## ⚠️ 注意事项
本插件已包含真寻AI插件默认的`hello`功能，使用本插件前请先**卸载**真寻的AI插件

## 🎉 使用
| 命令 | 参数 | 范围 | 说明 |
|:---:|:---:|:---:|:---:|
| `生成图片` | `prompt` | 私聊/群聊 | 根据给出文本生成图片,如果没有传入会询问用户 |
| `生成视频` | `prompt` | 私聊/群聊 | 根据给出文本生成视频,如果没有传入会询问用户 |
| `-` | `prompt` | 私聊/群聊 | 上下文对话，需要@Bot或叫Bot的名字 |

## ⚙️ 配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| `API_KEY` | **是** | `None` | 智谱ai的API KEY |
| `SOUL` | **否** | `你是真寻，你强大且无所不能` | AI的自定义人格 |

## 📚 插件依赖
如果插件报错了没有加载，说明真寻自动安装依赖失败了，请在Bot目录执行以下命令
```shell
poetry add zhipuai
```

## ⁉️ 已知问题
- ~~文生图/文生视频功能中，传入内容中不能包含空格和换行符，否侧插件不会处理~~(已修复)