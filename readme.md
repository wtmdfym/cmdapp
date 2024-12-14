# 关于cmdapp

    这是独立出来的可以在命令行中运行的app
    主要用于与GUI框架搭配，实现模块化

## 路线图

### 网络请求
- [x] Clientpool
- [x] async
- [ ] 绕过pixiv SNI封锁
- [ ] pixiv cat图片代理
### 支持的爬取对象
- [ ] id
- [ ] tag
- [ ] uid
- [ ] bookmarks
- [x] followings
- [ ] discovery
- [ ] ranking
### 支持的下载类型
- [x] illust
- [x] manga
- [ ] Series
- [x] novel
- [x] ugoira
- [ ] 小说插入的插画？
### GUI适配
- [x] pyQt
- [ ] dotnet (已放弃)
- [x] flutter (在flutter项目内)

## updates:
- 1.0.1
  - 优化代码，修复bug
  - 实现小说的获取
  - 新增记录作者最近作品的功能
  - 新增作者profileImageUrl的获取（未实现下载）
