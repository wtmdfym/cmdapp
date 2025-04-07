# 关于cmdapp

    这是独立出来的可以在命令行中运行的app
    主要用于与GUI框架搭配

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
- [x] bookmarks
- [x] followings
- [ ] discovery
- [ ] ranking
### 支持的下载类型
- [x] illust
- [x] manga
- [x] ugoira
- [x] novel
- [ ] series
- [ ] 小说插入的插画？
### GUI适配
- [x] pyQt
- [ ] dotnet (已放弃)
- [x] flutter (在flutter项目内)

## updates:
- 2.0.0
  - 优化代码结构
  - 支持获取收藏的作品
  - 更新类型检查方式，减少错误
  - 更新信息获取方式，适配pixiv新版接口 (不用再解析网页了，直接访问接口就可以获得作品信息(其实早就有了，但是现在html用不了了分析网络请求才发现))
- 1.0.3
  - 优化数据库操作
  - 修复bug
- 1.0.2
  - 优化下载器的代码。
  - 实现小说封面和作者profileImage的下载
- 1.0.1
  - 优化代码，修复bug
  - 实现小说的获取
  - 新增记录作者最近作品的功能
  - 新增作者profileImageUrl的获取（未实现下载）
