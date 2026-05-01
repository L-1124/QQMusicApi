
## [[0.5.3](https://github.com/L-1124/QQMusicApi/compare/v0.5.2..v0.5.3)] - 2026-05-01

### Bug 修复

* **(song)** 传递歌曲链接请求凭证 ([8667e8c](https://github.com/L-1124/QQMusicApi/commit/8667e8c16a071d5b2e96e91e90441db724d71169)) by [@L-1124](https://github.com/L-1124)
* 模型字段类型出现`int | str` ([ed2e450](https://github.com/L-1124/QQMusicApi/commit/ed2e4503fab162ebdabae7368ffd408584f1e91a)) by [@L-1124](https://github.com/L-1124)
* 手机登录没有正常返回验证链接 ([3f69c5d](https://github.com/L-1124/QQMusicApi/commit/3f69c5d3f51353c73ab1c9f5a6637e29dc0aebe4)) by [@L-1124](https://github.com/L-1124)
* [**breaking**] 拼写错误及其他问题 ([6bd129e](https://github.com/L-1124/QQMusicApi/commit/6bd129eed7d9d8bd1b76fbd6389840ee295d6802)) by [@Copilot](https://github.com/Copilot) in [#242](https://github.com/L-1124/QQMusicApi/pull/242)

### 功能更新

* **(api)** 统一分页参数，暴露搜索一致性参数 ([a3d3a5d](https://github.com/L-1124/QQMusicApi/commit/a3d3a5d36b0b1ee85628d4bafde17551ae76e5fe)) by [@L-1124](https://github.com/L-1124)
* **(login)** 细化登录异常体系并修正请求参数 ([fb9d2e6](https://github.com/L-1124/QQMusicApi/commit/fb9d2e6ed180b7188cc059b3a98ce67ec4760c0d)) by [@L-1124](https://github.com/L-1124) in [#245](https://github.com/L-1124/QQMusicApi/pull/245)

### 贡献者

* @L-1124
* @Copilot [#242](https://github.com/L-1124/QQMusicApi/pull/242)
* @github-actions[bot]

## [[0.5.2](https://github.com/L-1124/QQMusicApi/compare/v0.5.1..v0.5.2)] - 2026-04-18

### Bug 修复

* `UserFavSonglistResponse`jsonpath错误 ([2c54ebb](https://github.com/L-1124/QQMusicApi/commit/2c54ebb8d21a8ba02bb5b865a7ff0aa9aadcbc0d)) by [@L-1124](https://github.com/L-1124)
* `GetAlbumSongResponse`上游返回单个歌曲信息报错 ([adbdc40](https://github.com/L-1124/QQMusicApi/commit/adbdc4069f964125ca2228d36014f64893f3e69a)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(core)** 为 ResponsePager 添加 next 与 has_more ([0a63a26](https://github.com/L-1124/QQMusicApi/commit/0a63a264433bf37b5854064aa8ef95edba97adab)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* **(pagination)** 修正分页示例错误 ([c310450](https://github.com/L-1124/QQMusicApi/commit/c31045021034ce130136a17b458091c456998d53)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @renovate[bot] [#240](https://github.com/L-1124/QQMusicApi/pull/240)
* @github-actions[bot]

## [[0.5.1](https://github.com/L-1124/QQMusicApi/compare/v0.5.0..v0.5.1)] - 2026-04-13

### 功能更新

* 获取歌曲文件支持传入歌曲类型 ([a2ad367](https://github.com/L-1124/QQMusicApi/commit/a2ad3675ac56a501f8e08e761e12c68bf6155a98)) by [@L-1124](https://github.com/L-1124)
* [**breaking**] 重构歌曲文件获取逻辑，支持获取特殊类型的歌曲文件 ([5e31a48](https://github.com/L-1124/QQMusicApi/commit/5e31a4888cf3d4818b3cd59861ffc4d883c4ca1a)) by [@L-1124](https://github.com/L-1124)
* 接口请求支持更方便的下一页、换一批请求 ([98693f8](https://github.com/L-1124/QQMusicApi/commit/98693f86995df7a62ca705a46643afffb3306e4a)) by [@L-1124](https://github.com/L-1124) in [#235](https://github.com/L-1124/QQMusicApi/pull/235)

### 功能重构

* **(login)** 优化 MQTT 登录链路并替换 HTTP 重试实现 ([244e000](https://github.com/L-1124/QQMusicApi/commit/244e000c08dce6beb3ab46c7d266c361515b4b20)) by [@L-1124](https://github.com/L-1124) in [#237](https://github.com/L-1124/QQMusicApi/pull/237)

### 文档更新

* **(index)** 修正首页使用示例 ([ebafd9c](https://github.com/L-1124/QQMusicApi/commit/ebafd9cfc119c35e8b7a8fa16cd60abe81657707)) by [@L-1124](https://github.com/L-1124)
* 添加缺少的模块文档 ([376970e](https://github.com/L-1124/QQMusicApi/commit/376970ececc30e876342548ddacded06e48112d7)) by [@L-1124](https://github.com/L-1124)
* 更新 index.md ([d8e3668](https://github.com/L-1124/QQMusicApi/commit/d8e3668fdfb8e4766f8cf0cbc0e3bb9eece0bfd0)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @renovate[bot] [#238](https://github.com/L-1124/QQMusicApi/pull/238)
* @github-actions[bot]

## [[0.5.0](https://github.com/L-1124/QQMusicApi/compare/v0.4.1..v0.5.0)] - 2026-04-02

### Bug 修复

* **(LoginApi)** 限制手机验证码登录仅支持手机客户端 ([678694d](https://github.com/L-1124/QQMusicApi/commit/678694d4603fea0bd670b169be79c5eebbf64d98)) by [@L-1124](https://github.com/L-1124)
* **(api)** 修正登录与歌手接口平台契约 ([3f7f797](https://github.com/L-1124/QQMusicApi/commit/3f7f797bc09a4b32ea95409b6d13aab25b203758)) by [@L-1124](https://github.com/L-1124)
* **(client)** 修改请求参数构建错误 ([d28fe0e](https://github.com/L-1124/QQMusicApi/commit/d28fe0ec3a8551f5cccdeebeeabb2ab341613ef5)) by [@L-1124](https://github.com/L-1124)
* **(client)** 模块属性在同一实例内未能复用 ([2250227](https://github.com/L-1124/QQMusicApi/commit/2250227426a3d02e6af8d91ec4798ce34d7f7dc2)) by [@L-1124](https://github.com/L-1124)
* **(examples)** 修正下载示例的 CDN 访问 ([c24bd00](https://github.com/L-1124/QQMusicApi/commit/c24bd00bf9fd243d3583310e922eb85e07d4f5e5)) by [@L-1124](https://github.com/L-1124)
* **(login)** 更正刷新凭证方法命名 ([a81b738](https://github.com/L-1124/QQMusicApi/commit/a81b73812e17158b75cf61202ea43b71098ff6ee)) by [@L-1124](https://github.com/L-1124)
* **(login)** 明确二维码登录事件流与网络异常行为 ([0a348e4](https://github.com/L-1124/QQMusicApi/commit/0a348e48b17ac37cb9526d56026fcc3a40e8b919)) by [@L-1124](https://github.com/L-1124)
* **(mqtt)** 明确断链回调与调试日志语义 ([3e07727](https://github.com/L-1124/QQMusicApi/commit/3e07727586678710a00e31372878881b12a91491)) by [@L-1124](https://github.com/L-1124)
* **(song)** 修正 DTS_X 文件类型定义 ([992fe38](https://github.com/L-1124/QQMusicApi/commit/992fe3815a42cc0312d101f957790508f5dd3396)) by [@L-1124](https://github.com/L-1124)
* **(songlist)** 修正歌单写接口请求参数 ([004feb2](https://github.com/L-1124/QQMusicApi/commit/004feb25a72ac3a8a83eee9de54ba611f6c4f125)) by [@L-1124](https://github.com/L-1124)
* **(top)** 修复排行榜标签参数布尔透传 ([afff4fc](https://github.com/L-1124/QQMusicApi/commit/afff4fcf3303d1c07f1c2ca125a44b23ac2ee1c7)) by [@L-1124](https://github.com/L-1124)
* 更新登录模块以支持平台判断，修复二维码获取错误 ([bc1bdfa](https://github.com/L-1124/QQMusicApi/commit/bc1bdfa4bb8b67b48d952912c6bd0d1695425fba)) by [@L-1124](https://github.com/L-1124)
* 修复版本配置不对 ([9d71428](https://github.com/L-1124/QQMusicApi/commit/9d71428e3637cd19f410cb81c54f5fac57019392)) by [@L-1124](https://github.com/L-1124)
* resolve TypeError with Generic TypedDict on Python < 3.11 ([f142965](https://github.com/L-1124/QQMusicApi/commit/f14296511ca453bf20e196d44e1eb0a6e14ba12a)) by [@L-1124](https://github.com/L-1124)

### Config

* **(hooks)** 从 pre-commit 迁移到 prek ([2821122](https://github.com/L-1124/QQMusicApi/commit/2821122e668264e9e7f3d879e8cae536ac08d580)) by [@L-1124](https://github.com/L-1124)

### Revert

* **(core)** 重命名限流异常 ([271bc3b](https://github.com/L-1124/QQMusicApi/commit/271bc3b3f38fcc35d5e29dcd2d1553e5ee0cd8d5)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(Song)** 支持 dts:x 音质获取 ([5d8011a](https://github.com/L-1124/QQMusicApi/commit/5d8011a3a354a2f16415a2f322da23b717e26434)) by [@L-1124](https://github.com/L-1124)
* **(album)** 补充专辑响应模型 ([17cf26d](https://github.com/L-1124/QQMusicApi/commit/17cf26ded4e538278d787fa6c521bde05496b2db)) by [@L-1124](https://github.com/L-1124)
* **(api)** 添加 CDN 调度相关响应模型 ([56584ef](https://github.com/L-1124/QQMusicApi/commit/56584ef5be62f86edd130e2cc13fe8373b98eceb)) by [@L-1124](https://github.com/L-1124)
* **(client)** 添加自动重试能力 ([a46c02b](https://github.com/L-1124/QQMusicApi/commit/a46c02b112adff8c919cc653d408ccc261324b89)) by [@L-1124](https://github.com/L-1124)
* **(comment)** 补充评论响应模型 ([9781045](https://github.com/L-1124/QQMusicApi/commit/9781045b466c143b61bdd53e8ddcf3fd2ddd6a52)) by [@L-1124](https://github.com/L-1124)
* **(credential)** 支持凭证过期判断并完善文档 ([754752f](https://github.com/L-1124/QQMusicApi/commit/754752fbbdd09895ae460e123ddc87cc462d84cc)) by [@L-1124](https://github.com/L-1124)
* **(login)** 完善刷新参数与过期错误识别 ([5049b4e](https://github.com/L-1124/QQMusicApi/commit/5049b4e61227c8c10132de649725d075d5e2a62c)) by [@L-1124](https://github.com/L-1124)
* **(login)** 引入登录会话对象 ([84922ea](https://github.com/L-1124/QQMusicApi/commit/84922eaba08a34ff859eddd5765fd568ed1e2e5d)) by [@L-1124](https://github.com/L-1124)
* **(lyric)** 补充歌词响应模型 ([946184b](https://github.com/L-1124/QQMusicApi/commit/946184b4ba48735e50c614c12a78e735dd9cfaa9)) by [@L-1124](https://github.com/L-1124)
* **(models)** 完善封面链接获取 ([ded12d6](https://github.com/L-1124/QQMusicApi/commit/ded12d6cebcd09a52db136c55a3f7bc0336ec60e)) by [@L-1124](https://github.com/L-1124)
* **(models)** 补充推荐响应模型 ([18c1935](https://github.com/L-1124/QQMusicApi/commit/18c19357b3b327610bc122410a77804fd398c5df)) by [@L-1124](https://github.com/L-1124)
* **(models)** 新增通用响应基类并支持 JSONPath 字段提取 ([36084c6](https://github.com/L-1124/QQMusicApi/commit/36084c6443f90f71028d651d71ede0b15f8fe45a)) by [@L-1124](https://github.com/L-1124)
* **(mv)** 新增 MV 响应模型并接入类型化解析 ([8c690e3](https://github.com/L-1124/QQMusicApi/commit/8c690e339959f08483b99943049bcfc5f6015c74)) by [@L-1124](https://github.com/L-1124)
* **(search)** 新增搜索响应模型并接入类型化解析 ([ffa12ca](https://github.com/L-1124/QQMusicApi/commit/ffa12cad0963b61ea8723827e6653e2af116f935)) by [@L-1124](https://github.com/L-1124)
* **(singer)** 补充歌手响应模型 ([c3697ad](https://github.com/L-1124/QQMusicApi/commit/c3697ad1682c6813bff2059e6b0972b7ffbbabfb)) by [@L-1124](https://github.com/L-1124)
* **(song)** 补充歌曲接口模型 ([828268d](https://github.com/L-1124/QQMusicApi/commit/828268db92190432ed88f0db9231cae37095c59e)) by [@L-1124](https://github.com/L-1124)
* **(song)** 新增多音质支持（7.1全景声/杜比全景声/NAC/黑胶） ([f7296fc](https://github.com/L-1124/QQMusicApi/commit/f7296fc26675d2cbdb5e94340fce5d4f53374921)) by [@L-1124](https://github.com/L-1124)
* **(songlist)** 补充歌单响应模型 ([c289c88](https://github.com/L-1124/QQMusicApi/commit/c289c889afe2f0d0a0a852c86b9b3777ff6f253a)) by [@L-1124](https://github.com/L-1124)
* **(top)** 补充排行榜响应模型 ([4175d5b](https://github.com/L-1124/QQMusicApi/commit/4175d5be573e7d6628c61503840a0340955e25e9)) by [@L-1124](https://github.com/L-1124)
* **(user)** 补充用户响应模型 ([e1f1b8c](https://github.com/L-1124/QQMusicApi/commit/e1f1b8cf3a94ae2801aad6b2bbee9538fc36241d)) by [@L-1124](https://github.com/L-1124)
* **(user)** 自动为主页和会员接口补占位凭证 ([ab53d36](https://github.com/L-1124/QQMusicApi/commit/ab53d36e0ebbcf1268fbb2a9f71fa164fc2f64f8)) by [@L-1124](https://github.com/L-1124)
* **(user)** 移除 get_euin 和 get_musicid 接口 ([4975fdf](https://github.com/L-1124/QQMusicApi/commit/4975fdf292a4e86f3668df286e7208ec5876a075)) by [@L-1124](https://github.com/L-1124)
* 自定义qimei获取时设备文件缓存路径 ([4a7bc21](https://github.com/L-1124/QQMusicApi/commit/4a7bc21546c00fbddb85ddf9354f9338ab6290e8)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* **(api)** 统一请求架构并重构模块与批处理模型 ([7099103](https://github.com/L-1124/QQMusicApi/commit/7099103d92587de2c7d7c1a17be48587b1f9b53d)) by [@L-1124](https://github.com/L-1124) in [#226](https://github.com/L-1124/QQMusicApi/pull/226)
* **(core)** 将 RateLimitError 重命名为 GlobalAuthFailedError ([b6b90c5](https://github.com/L-1124/QQMusicApi/commit/b6b90c561db42ba835f540616544bf9bfc7573e7)) by [@L-1124](https://github.com/L-1124)
* **(core)** 收敛核心层数据校验与辅助逻辑 ([2b7cc32](https://github.com/L-1124/QQMusicApi/commit/2b7cc32c8c441322a77e8fb96b5237282b98955a)) by [@L-1124](https://github.com/L-1124)
* **(core)** 收敛核心层异常与平台语义 ([57de232](https://github.com/L-1124/QQMusicApi/commit/57de232b14c03f47c5960db144dd02a2bc1b8271)) by [@L-1124](https://github.com/L-1124)
* **(login)** 重构登录流程模块职责 ([969b94c](https://github.com/L-1124/QQMusicApi/commit/969b94ce402ddfea3c48227d3a91984389e9e235)) by [@L-1124](https://github.com/L-1124)
* **(models)** 按测试回退响应模型默认值 ([8edca85](https://github.com/L-1124/QQMusicApi/commit/8edca85df834b83e7bb2b7c2826f56a8c37c68c4)) by [@L-1124](https://github.com/L-1124)
* **(models)** 统一基础模型别名映射 ([d34a7e7](https://github.com/L-1124/QQMusicApi/commit/d34a7e736fd71c529c7efc098276aba82737886c)) by [@L-1124](https://github.com/L-1124)
* **(mqtt)** 使用 paho-mqtt 重构客户端实现 ([644ecee](https://github.com/L-1124/QQMusicApi/commit/644ecee3c15a05d2b1f6c0a01c49635936bcbc72)) by [@L-1124](https://github.com/L-1124)
* **(search)** 统一搜索类型枚举 ([37fddf8](https://github.com/L-1124/QQMusicApi/commit/37fddf8178e33e7704159dd915acd93a0410780b)) by [@L-1124](https://github.com/L-1124)
* **(song)** 调整歌曲取链参数支持 ([d7d4ab6](https://github.com/L-1124/QQMusicApi/commit/d7d4ab69f55395372dd0fd5e5f52f435dd55215e)) by [@L-1124](https://github.com/L-1124)
* **(song)** 去除歌曲链接分组与自动拼接并调整示例 ([04624fd](https://github.com/L-1124/QQMusicApi/commit/04624fd7bee01446b6094f0f4267c04c6a82daff)) by [@L-1124](https://github.com/L-1124)
* **(tests)** 重构测试文件 ([62fac87](https://github.com/L-1124/QQMusicApi/commit/62fac873ccc33507182eb54fb537363eb979234f)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* **(license)** 切换 GPL 协议说明 ([45c74ad](https://github.com/L-1124/QQMusicApi/commit/45c74ad7be35b685dee3601a8ae4eb0c6bbed85c)) by [@L-1124](https://github.com/L-1124)
* **(models)** 完善模型注释 ([c893f9d](https://github.com/L-1124/QQMusicApi/commit/c893f9d09e82f17385c0f3048ac26f4c0d531c0d)) by [@L-1124](https://github.com/L-1124)
* 更新文档配置文件说明 ([d42966a](https://github.com/L-1124/QQMusicApi/commit/d42966a265f15a74eb0348eda35734cf84a5911a)) by [@L-1124](https://github.com/L-1124)
* 更新文档 ([9a13de2](https://github.com/L-1124/QQMusicApi/commit/9a13de2b6aae6c6df8abe3e4879aed819f06d278)) by [@L-1124](https://github.com/L-1124)
* 更新 README.md.修正图像链接，优化格式和内容，增强可读性 ([7a42d6f](https://github.com/L-1124/QQMusicApi/commit/7a42d6f66ef756ba737dbf6eb672b7293bf06996)) by [@L-1124](https://github.com/L-1124)
* 添加评论 API 文档并更新用户 API 文档注释 ([618bf5a](https://github.com/L-1124/QQMusicApi/commit/618bf5a482eb81bba49883c39afbbae4ea3b3077)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]

## [[0.4.1](https://github.com/L-1124/QQMusicApi/compare/v0.4.0..v0.4.1)] - 2025-12-28

### 文档更新

* 更新文档和代码注释 ([62d41ee](https://github.com/L-1124/QQMusicApi/commit/62d41eecbfc00541f4910955625c6c1ee14cc13a)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124

## [[0.4.0](https://github.com/L-1124/QQMusicApi/compare/v0.3.6..v0.4.0)] - 2025-12-27

### Bug 修复

* 优先从 purl 获取歌曲链接并更新 ct 参数 ([3ccc5da](https://github.com/L-1124/QQMusicApi/commit/3ccc5daaf0b3d35a4b7375824b213c07687fa992)) by [@jinzhongjia](https://github.com/jinzhongjia) in [#219](https://github.com/L-1124/QQMusicApi/pull/219)

### 功能更新

* 添加获取时刻评论的功能并且修改API返回为原始数据 ([3c7f6ef](https://github.com/L-1124/QQMusicApi/commit/3c7f6eff438a0c403d36b87e3559e7a5416425fb)) by [@L-1124](https://github.com/L-1124)
* 删除API缓存功能 ([36b04f7](https://github.com/L-1124/QQMusicApi/commit/36b04f785b6202bd6e95b26da3d9971e2ecc6bbf)) by [@L-1124](https://github.com/L-1124)
* 支持QQ音乐APP扫码登录 ([9f8c855](https://github.com/L-1124/QQMusicApi/commit/9f8c855210c23fa38885d4d150419ec551bb6d03)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* 移除 API 请求中的 exclude_params 参数 ([59694d3](https://github.com/L-1124/QQMusicApi/commit/59694d39d2064e5a08d0eccf7a1efbcc300cb919)) by [@L-1124](https://github.com/L-1124)
* 优化 ApiRequest Cookies 管理 ([34a5876](https://github.com/L-1124/QQMusicApi/commit/34a5876fc54120fc049469b845ace4da94459413)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* Update README links and image sources ([7c09d07](https://github.com/L-1124/QQMusicApi/commit/7c09d07468e6b35802d558c73e81f490a99533bc)) by [@L-1124](https://github.com/L-1124)
* 更新 README.md ([ebf3347](https://github.com/L-1124/QQMusicApi/commit/ebf33472e0ff1e532b378fa353bf9ce51caf2d0a)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124
* @jinzhongjia [#219](https://github.com/L-1124/QQMusicApi/pull/219)
* @renovate[bot] [#190](https://github.com/L-1124/QQMusicApi/pull/190)

## [[0.3.6](https://github.com/L-1124/QQMusicApi/compare/v0.3.5..v0.3.6)] - 2025-08-22

### Bug 修复

* **(comment)** 获取歌曲热评时页码错误 ([b8d2d3d](https://github.com/L-1124/QQMusicApi/commit/b8d2d3dfc117b74d0d209b697288dafe1f98d360)) by [@L-1124](https://github.com/L-1124)
* 错误地将歌曲链接缓存 ([eec0100](https://github.com/L-1124/QQMusicApi/commit/eec01001e24d7fa8135b40296b300657a75e5c17)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(comment)** 获取推荐评论 ([f4b1eda](https://github.com/L-1124/QQMusicApi/commit/f4b1eda6bd971bfe08351d83c2964d035b7a8551)) by [@L-1124](https://github.com/L-1124)
* **(comment)** 获取歌曲最新评论 ([1ae5875](https://github.com/L-1124/QQMusicApi/commit/1ae58759d771d9fbfd7e4431cf55525a58cf0463)) by [@L-1124](https://github.com/L-1124)
* 获取歌曲评论数量 ([f484e7f](https://github.com/L-1124/QQMusicApi/commit/f484e7f9dc8c2911fe404f843161e717aa615184)) by [@L-1124](https://github.com/L-1124)
* 获取雷达推荐歌曲 ([04b5923](https://github.com/L-1124/QQMusicApi/commit/04b59238b2d9a5af3533844b178a990b0a1b550e)) by [@L-1124](https://github.com/L-1124)
* 支持获取推荐歌单，推荐新歌 ([460be11](https://github.com/L-1124/QQMusicApi/commit/460be1125af242c409ff91d06038b25f305702fd)) by [@L-1124](https://github.com/L-1124)
* 升级加密算法 ([2f01428](https://github.com/L-1124/QQMusicApi/commit/2f01428c3b23ec29691100c9417bba205ae04f83)) by [@L-1124](https://github.com/L-1124)
* 支持主页推荐，猜你喜欢获取 ([64469cc](https://github.com/L-1124/QQMusicApi/commit/64469ccfaa1404b7e43a66e3ad3927908df35f11)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* **(contributing)** 更新贡献文档 ([e834b32](https://github.com/L-1124/QQMusicApi/commit/e834b325215be02caef1883e767a03b95aeeca6b)) by [@L-1124](https://github.com/L-1124)
* 修改文档错误 ([a01cf0f](https://github.com/L-1124/QQMusicApi/commit/a01cf0f36c0edaf610d1b435c154c1f33b4493d8)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124
* @renovate[bot] [#188](https://github.com/L-1124/QQMusicApi/pull/188)

## [[0.3.5](https://github.com/L-1124/QQMusicApi/compare/v0.3.4..v0.3.5)] - 2025-07-29

### Bug 修复

* **(login)** “限制设备数量”导致无法登录时无任何提示 ([faeca45](https://github.com/L-1124/QQMusicApi/commit/faeca45381bd3bcc1efbc8d92fbfc86bdfda9baa)) by [@L-1124](https://github.com/L-1124)
* 修复请求可变参数错误 ([0b3dea8](https://github.com/L-1124/QQMusicApi/commit/0b3dea8288a3d7236ef04560896c465d3bc6efda)) by [@L-1124](https://github.com/L-1124)
* update qq qrlogin module/method ([f24adb8](https://github.com/L-1124/QQMusicApi/commit/f24adb8adecb0e476c9ca25f72b8516bf616133a)) by [@aynakeya](https://github.com/aynakeya) in [#178](https://github.com/L-1124/QQMusicApi/pull/178)
* 'RequestGroup' 返回数据序号错误 ([17fbd53](https://github.com/L-1124/QQMusicApi/commit/17fbd53cce7bc34cc071080d02ed8cad2bd7d1a3)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* 添加获取精彩评论（歌曲热评）的能力 ([99947c8](https://github.com/L-1124/QQMusicApi/commit/99947c84bbd42eb5d5100567dd59ec7c6ea6bfdc)) by [@Aas-ee](https://github.com/Aas-ee) in [#161](https://github.com/L-1124/QQMusicApi/pull/161)

### 文档更新

* **(comment)** 增加歌曲热评返回参数注释 ([418b032](https://github.com/L-1124/QQMusicApi/commit/418b0324d7638f28a69e74b0318c1f2f43d8496c)) by [@Aas-ee](https://github.com/Aas-ee) in [#164](https://github.com/L-1124/QQMusicApi/pull/164)

### 贡献者

* @github-actions[bot]
* @L-1124
* @renovate[bot] [#167](https://github.com/L-1124/QQMusicApi/pull/167)
* @aynakeya [#178](https://github.com/L-1124/QQMusicApi/pull/178)
* @Aas-ee [#164](https://github.com/L-1124/QQMusicApi/pull/164)

## [[0.3.4](https://github.com/L-1124/QQMusicApi/compare/v0.3.3..v0.3.4)] - 2025-03-20

### Bug 修复

* `is_expired` 和 `can_refresh` 判断错误 ([a28a473](https://github.com/L-1124/QQMusicApi/commit/a28a47371380942d45c8b565acb38083e45ac8f0)) by [@L-1124](https://github.com/L-1124)
* modify fields to filter of `get_friend` ([660ca49](https://github.com/L-1124/QQMusicApi/commit/660ca4991afac86afabfb45ce966a50e5416f7b9)) by [@aurora0x27](https://github.com/aurora0x27) in [#151](https://github.com/L-1124/QQMusicApi/pull/151)
* `credential` 未强制为关键字参数 ([147ab2d](https://github.com/L-1124/QQMusicApi/commit/147ab2d118e3aa3aaa2c99fa0ce48ddddb166527)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* 重构 Web Port Parser ([1cfb62d](https://github.com/L-1124/QQMusicApi/commit/1cfb62d502a79bd3dfaeb1de44a7d9192eb4911d)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* Web Port 文档 ([ffc8842](https://github.com/L-1124/QQMusicApi/commit/ffc884230ab7c12b6d392923474394ca7b0aa9de)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124
* @aurora0x27 [#151](https://github.com/L-1124/QQMusicApi/pull/151)
* @renovate[bot] [#142](https://github.com/L-1124/QQMusicApi/pull/142)

## [[0.3.3](https://github.com/L-1124/QQMusicApi/compare/v0.3.2..v0.3.3)] - 2025-03-15

### Bug 修复

* **(songlist)** 第一次获取最大歌曲量 ([a3bc27e](https://github.com/L-1124/QQMusicApi/commit/a3bc27ebf4be16868f9047639ea94c01dc0bbcd8)) by [@liuhangbin](https://github.com/liuhangbin) in [#147](https://github.com/L-1124/QQMusicApi/pull/147)
* 修复设置全局Session未生效 ([73e8cba](https://github.com/L-1124/QQMusicApi/commit/73e8cba4b466ab6ee4550264f32149cecd99e692)) by [@L-1124](https://github.com/L-1124)
* 部分API使用缓存 ([cd58f01](https://github.com/L-1124/QQMusicApi/commit/cd58f01a605a6599de6d88b08d073b6d21b29b72)) by [@L-1124](https://github.com/L-1124)
* 修复`get_singer_list_index`返回为空报错 ([f9993a9](https://github.com/L-1124/QQMusicApi/commit/f9993a908f2dd1a56acbd6fce926049aa9a99b3b)) by [@L-1124](https://github.com/L-1124)
* Docker 运行出错 ([47295db](https://github.com/L-1124/QQMusicApi/commit/47295db3b1fd03b23c29ae750fc71c2ddf3e575b)) by [@L-1124](https://github.com/L-1124)
* 修复qimei请求失败 ([0a781dd](https://github.com/L-1124/QQMusicApi/commit/0a781dd8b6b76d6abc4bbd6fc6709676a525c667)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(Songlist)** 添加歌单处理函数 ([49eeafd](https://github.com/L-1124/QQMusicApi/commit/49eeafdfff58451a010b949f61d7af0e8d72afd8)) by [@liuhangbin](https://github.com/liuhangbin) in [#144](https://github.com/L-1124/QQMusicApi/pull/144)
* 添加日志记录功能以跟踪Session的创建、设置和清除 ([d89e046](https://github.com/L-1124/QQMusicApi/commit/d89e046520def6586dfef4aa93f2c39d7c32865e)) by [@L-1124](https://github.com/L-1124)
* 优化返回注释 ([0f5da78](https://github.com/L-1124/QQMusicApi/commit/0f5da78aad5221fce49b249e988d2740b861e17c)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 更新 README.md ([ef6c07c](https://github.com/L-1124/QQMusicApi/commit/ef6c07c57b667fa1681df7ac0851a95863d1d372)) by [@L-1124](https://github.com/L-1124)
* 修改 changelog 生成规则 ([da3e829](https://github.com/L-1124/QQMusicApi/commit/da3e829f5d1934ceb09bf6c97c84250f6bede07e)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124
* @liuhangbin [#147](https://github.com/L-1124/QQMusicApi/pull/147)

## [[0.3.2](https://github.com/L-1124/QQMusicApi/compare/v0.3.1..v0.3.2)] - 2025-03-02

### Bug 修复

* comm 参数未合并 ([d8cac55](https://github.com/L-1124/QQMusicApi/commit/d8cac55c1d1a27d0f08ed9027139265cd97e8626)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124

## [[0.3.1](https://github.com/L-1124/QQMusicApi/compare/v0.3.0..v0.3.1)] - 2025-03-02

### Bug 修复

* Cookies 导入为 Credential 时错误 ([30e40e3](https://github.com/L-1124/QQMusicApi/commit/30e40e3ece7ea61117d59bdef73d857451f5e495)) by [@L-1124](https://github.com/L-1124)
* `RequsetGroup` 请求数量过多报错 ([ff2c65b](https://github.com/L-1124/QQMusicApi/commit/ff2c65b3b5d40d4d208b9d03edd38b580fc3ec7a)) by [@L-1124](https://github.com/L-1124)
* RequestGroup 解析数据错误 ([257f28f](https://github.com/L-1124/QQMusicApi/commit/257f28f2a6c3b8b5353d04aad3b3c28b1b16b9f9)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(singer)** 添加获取全部歌曲，专辑，MV调用 ([fe48011](https://github.com/L-1124/QQMusicApi/commit/fe4801156d3938b84ada827a1e253b00cc9555d9)) by [@liuhangbin](https://github.com/liuhangbin) in [#140](https://github.com/L-1124/QQMusicApi/pull/140)
* 默认开启 Http2 ([b6ea59e](https://github.com/L-1124/QQMusicApi/commit/b6ea59ec71ce669fe6f47e7c45017d0d0eb13d4d)) by [@L-1124](https://github.com/L-1124)
* 手动清除API缓存 ([4ad301f](https://github.com/L-1124/QQMusicApi/commit/4ad301f5e4f6d079cc15b87e84fdc58161461f51)) by [@L-1124](https://github.com/L-1124)
* 优先通过 Credential 字段判断是否过期 ([e6dd11d](https://github.com/L-1124/QQMusicApi/commit/e6dd11d5200950b51feb73b855edd5942251fdb8)) by [@L-1124](https://github.com/L-1124)
* 使用 OrJson 加快 json 解析 ([fe1c430](https://github.com/L-1124/QQMusicApi/commit/fe1c430cf6b3423a83a980800e211893bd17030e)) by [@L-1124](https://github.com/L-1124)

### 性能优化

* **(singer)** 优化请求性能 ([4245dd9](https://github.com/L-1124/QQMusicApi/commit/4245dd928843b0e89c6c7b15e4b399376eeb59f2)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 补充代理配置 ([9977ec9](https://github.com/L-1124/QQMusicApi/commit/9977ec960418e108880cbdbe54dd6cebc25df36b)) by [@L-1124](https://github.com/L-1124)
* 更新文档 ([c4312ae](https://github.com/L-1124/QQMusicApi/commit/c4312ae1a8d0045442fb8e91bd9d0109429e59e1)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]
* @renovate[bot] [#132](https://github.com/L-1124/QQMusicApi/pull/132)
* @liuhangbin [#140](https://github.com/L-1124/QQMusicApi/pull/140)

## [[0.3.0](https://github.com/L-1124/QQMusicApi/compare/v0.2.2..v0.3.0)] - 2025-02-23

### Bug 修复

* **(singer)** 修复地区代码错误 ([03023cf](https://github.com/L-1124/QQMusicApi/commit/03023cf36bf4fef33ec0580ff4e59a437648c570)) by [@liuhangbin](https://github.com/liuhangbin) in [#127](https://github.com/L-1124/QQMusicApi/pull/127)
* 命名错误 ([20d8c27](https://github.com/L-1124/QQMusicApi/commit/20d8c2766b22399bd8f7ad21506d6811981cf47c)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(Singer)** 支持根据首字母来过滤歌手列表 ([61af369](https://github.com/L-1124/QQMusicApi/commit/61af3696c551f61912c93775cb9004f05d527c2f)) by [@liuhangbin](https://github.com/liuhangbin) in [#129](https://github.com/L-1124/QQMusicApi/pull/129)
* **(song)** add get_fav_num function ([ad3b4e5](https://github.com/L-1124/QQMusicApi/commit/ad3b4e5f89f99da680e74cb2c9dd5e56b50a772f)) by [@liuhangbin](https://github.com/liuhangbin) in [#135](https://github.com/L-1124/QQMusicApi/pull/135)
* 支持 Docker 部署 ([0e81cbc](https://github.com/L-1124/QQMusicApi/commit/0e81cbcd5472873c654ea17ba8d938cf0f8b1647)) by [@L-1124](https://github.com/L-1124)
* 新增 `get_singer_list_index` 歌手列表查询 ([803b486](https://github.com/L-1124/QQMusicApi/commit/803b486a91bd2f7b100dc211d3b581430ff91b67)) by [@liguobao](https://github.com/liguobao) in [#124](https://github.com/L-1124/QQMusicApi/pull/124)
* 缓存功能 ([4db7ac8](https://github.com/L-1124/QQMusicApi/commit/4db7ac8ff97052504dba12c2526f6f1894fbf3e6)) by [@L-1124](https://github.com/L-1124)
* 支持 WEB API ([2ed9199](https://github.com/L-1124/QQMusicApi/commit/2ed91995c5d1e906a2951666bb1dd845a35b0e89)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* 重构 Python API ([fc917df](https://github.com/L-1124/QQMusicApi/commit/fc917df2d00a378bbeb0225f9ea520fffa6d54ba)) by [@L-1124](https://github.com/L-1124) in [#110](https://github.com/L-1124/QQMusicApi/pull/110)

### 性能优化

* 优化Session获取 ([e77e87f](https://github.com/L-1124/QQMusicApi/commit/e77e87f2bf958f9391ff1a1f88c85bc3a4526b83)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* API 编写指南 ([dff5819](https://github.com/L-1124/QQMusicApi/commit/dff58197c329ff2e519233d0acb68b7e60b32011)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]
* @liuhangbin [#135](https://github.com/L-1124/QQMusicApi/pull/135)
* @liguobao [#124](https://github.com/L-1124/QQMusicApi/pull/124)
* @renovate[bot] [#118](https://github.com/L-1124/QQMusicApi/pull/118)

## [[0.2.2](https://github.com/L-1124/QQMusicApi/compare/v0.2.1..v0.2.2)] - 2025-01-25

### Bug 修复

* 逐字歌词丢失换行符 ([6a5072e](https://github.com/L-1124/QQMusicApi/commit/6a5072e5e424ce79635bbf937032256494f8172c)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @github-actions[bot]
* @L-1124

## [[0.2.1](https://github.com/L-1124/QQMusicApi/compare/v0.2.0..v0.2.1)] - 2025-01-04

### Bug 修复

* 修复扫码登录报错 ([bc4d272](https://github.com/L-1124/QQMusicApi/commit/bc4d27209a999e90acf040f0398ec9d5e34e96ae)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* [**breaking**] 不再支持 Python 3.9 ([4d51d23](https://github.com/L-1124/QQMusicApi/commit/4d51d23d282de7e39d5460779462541e378298b7)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 修改字体链接 ([9bd6ea2](https://github.com/L-1124/QQMusicApi/commit/9bd6ea2b97b648e5306de3eb889012b1774aa945)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]
* @renovate[bot] [#99](https://github.com/L-1124/QQMusicApi/pull/99)

## [[0.2.0](https://github.com/L-1124/QQMusicApi/compare/v0.1.11..v0.2.0)] - 2024-12-28

### Bug 修复

* **(deps)** update dependency cryptography to v44 ([eb2cf36](https://github.com/L-1124/QQMusicApi/commit/eb2cf3610422819c4846b475a4067f1a473e25fc)) by [@renovate[bot]](https://github.com/renovate[bot]) in [#81](https://github.com/L-1124/QQMusicApi/pull/81)
* **(search)** 修复搜索`singer`报错,`audio_album`无结果 ([c3ac3c3](https://github.com/L-1124/QQMusicApi/commit/c3ac3c3e2f2d7eb91fde595bb00518816b520455)) by [@L-1124](https://github.com/L-1124)
* logging 不生效 ([0118697](https://github.com/L-1124/QQMusicApi/commit/01186973a5cbc1fb0b75b0428743fddb786ea861)) by [@L-1124](https://github.com/L-1124)
* QQ 刷新 Credential 失败 ([2901a0c](https://github.com/L-1124/QQMusicApi/commit/2901a0c3df99741be8c35b888eae5bcde34a6239)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(credential)** 从字符串创建 Credential ([025cb30](https://github.com/L-1124/QQMusicApi/commit/025cb3015fd60d56158aef8f0f3ea569cdae73ef)) by [@L-1124](https://github.com/L-1124)
* 支持加密接口 ([768a3f3](https://github.com/L-1124/QQMusicApi/commit/768a3f3d4a0f9ac604777951441a99eb7289fbe2)) by [@L-1124](https://github.com/L-1124)
* 使用`Session`管理请求 ([7485870](https://github.com/L-1124/QQMusicApi/commit/748587083e69659a3571a93ee4e3fedfb5497a58)) by [@L-1124](https://github.com/L-1124) in [#87](https://github.com/L-1124/QQMusicApi/pull/87)

### 功能重构

* 重构`utils.utils`为`utils.common` ([8a99daf](https://github.com/L-1124/QQMusicApi/commit/8a99dafb7f75806a152ea1bd8d95b30ab4b871a4)) by [@L-1124](https://github.com/L-1124)
* 重构 QIMEI 获取 ([7f0aa0f](https://github.com/L-1124/QQMusicApi/commit/7f0aa0ffad5c4617c881ce58f3213a9c2f046084)) by [@L-1124](https://github.com/L-1124)

### 构建配置

* 更新 ruff 配置 ([b81311b](https://github.com/L-1124/QQMusicApi/commit/b81311b8db7fb6a2b82155f3fc5aa51bf65b5959)) by [@L-1124](https://github.com/L-1124)
* 从 PDM 迁移到 UV ([804c992](https://github.com/L-1124/QQMusicApi/commit/804c992ebc1573fe1520846b9a7c90f41b83c144)) by [@L-1124](https://github.com/L-1124) in [#78](https://github.com/L-1124/QQMusicApi/pull/78)
* Update pdm.lock ([e977b5b](https://github.com/L-1124/QQMusicApi/commit/e977b5b4765a731700470486438b364c889526f9)) by [@github-actions[bot]](https://github.com/github-actions[bot]) in [#76](https://github.com/L-1124/QQMusicApi/pull/76)

### 贡献者

* @L-1124
* @github-actions[bot]
* @renovate[bot] [#91](https://github.com/L-1124/QQMusicApi/pull/91)

## [[0.1.11](https://github.com/L-1124/QQMusicApi/compare/v0.1.10..v0.1.11)] - 2024-11-10

### Bug 修复

* 单次获取歌曲链接过多报错 ([e366f6d](https://github.com/L-1124/QQMusicApi/commit/e366f6d842abe94be264bc3e9d62b663cb9afdcc)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]

## [[0.1.10](https://github.com/L-1124/QQMusicApi/compare/v0.1.9..v0.1.10)] - 2024-11-09

### 功能更新

* 支持 logging ([35e94ca](https://github.com/L-1124/QQMusicApi/commit/35e94cad6574f11c23bf9bff9a2b9ed23e9882d5)) by [@L-1124](https://github.com/L-1124) in [#73](https://github.com/L-1124/QQMusicApi/pull/73)

### 构建配置

* Update pdm.lock ([299299b](https://github.com/L-1124/QQMusicApi/commit/299299b907ccdf3f5b9ac7052bd207e45bf24c0a)) by [@github-actions[bot]](https://github.com/github-actions[bot]) in [#74](https://github.com/L-1124/QQMusicApi/pull/74)

### 贡献者

* @L-1124
* @github-actions[bot] [#74](https://github.com/L-1124/QQMusicApi/pull/74)

## [[0.1.9](https://github.com/L-1124/QQMusicApi/compare/v0.1.8..v0.1.9)] - 2024-10-26

### Bug 修复

* MVApi 注释错误 ([0ace5cf](https://github.com/L-1124/QQMusicApi/commit/0ace5cf2c6f5b7b03c5f63f396d45be64edfb35b)) by [@L-1124](https://github.com/L-1124)
* 修复获取逐字歌词未解析问题 ([26929f2](https://github.com/L-1124/QQMusicApi/commit/26929f26e4f61c5d5f68161cbe360f437ff50820)) by [@L-1124](https://github.com/L-1124) in [#67](https://github.com/L-1124/QQMusicApi/pull/67)

### 功能更新

* 支持获取专辑封面链接 ([7fe9644](https://github.com/L-1124/QQMusicApi/commit/7fe964427f6c126a70173554bcdc5284e54331b2)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* **(LoginApi)** [**breaking**] 重构 LoginApi ([9244c0e](https://github.com/L-1124/QQMusicApi/commit/9244c0ebe8981ca2a00afb1fe367175b1b1a39c0)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 自动生成 Release Notes ([5b3dfa6](https://github.com/L-1124/QQMusicApi/commit/5b3dfa6e9ec89ad00c0d88f71b4ac16f8732ef39)) by [@L-1124](https://github.com/L-1124)
* 更新 Readme ([485d988](https://github.com/L-1124/QQMusicApi/commit/485d988c991b833d0f79ae7f86e5d1057fdff0dc)) by [@L-1124](https://github.com/L-1124)
* Update exceptions.md ([a86f4a1](https://github.com/L-1124/QQMusicApi/commit/a86f4a1d918fae7df8bccb25faab5b0751e91ae4)) by [@L-1124](https://github.com/L-1124)

### 构建配置

* 更新依赖版本 ([1a42f97](https://github.com/L-1124/QQMusicApi/commit/1a42f9707939ec86f0d0544ef771875018589782)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
* @github-actions[bot]

## [[0.1.8](https://github.com/L-1124/QQMusicApi/compare/v0.1.7..v0.1.8)] - 2024-10-05

### 功能更新

* `get_song_urls` 更好的 Typing Hints ([02a62f5](https://github.com/L-1124/QQMusicApi/commit/02a62f57d083b2b5d7c98ad5078ede521c99045d)) by [@L-1124](https://github.com/L-1124) in [#62](https://github.com/L-1124/QQMusicApi/pull/62)
* 支持 UserApi ([7a99429](https://github.com/L-1124/QQMusicApi/commit/7a994290cb298a868963d325dccab4a908e5fd9a)) by [@L-1124](https://github.com/L-1124) in [#59](https://github.com/L-1124/QQMusicApi/pull/59)
* 支持检测凭证是否过期 ([3a2b011](https://github.com/L-1124/QQMusicApi/commit/3a2b011445479327dd433bc934685ac0088b1ef7)) by [@L-1124](https://github.com/L-1124) in [#61](https://github.com/L-1124/QQMusicApi/pull/61)
* 支持在事件循环已经运行时同步执行异步代码 ([b8190f5](https://github.com/L-1124/QQMusicApi/commit/b8190f5663ca6c61ff622f18d0c14d065fe5c38d)) by [@L-1124](https://github.com/L-1124) in [#60](https://github.com/L-1124/QQMusicApi/pull/60)
* 支持 ogg 640kbps 获取 ([fe1660e](https://github.com/L-1124/QQMusicApi/commit/fe1660ed86da7e1bb1bbc05b163af4acfd54205e)) by [@L-1124](https://github.com/L-1124) in [#58](https://github.com/L-1124/QQMusicApi/pull/58)

### 功能重构

* 重构 ApiException ([11298e9](https://github.com/L-1124/QQMusicApi/commit/11298e9c3f225b280ad654ab0b63d4c7455dc895)) by [@L-1124](https://github.com/L-1124) in [#64](https://github.com/L-1124/QQMusicApi/pull/64)

### 贡献者

* @L-1124

## [[0.1.7](https://github.com/L-1124/QQMusicApi/compare/v0.1.6..v0.1.7)] - 2024-09-15

### 功能更新

* 支持 LyricApi ([a5534b5](https://github.com/L-1124/QQMusicApi/commit/a5534b5975bd95e45a5022eafd994362d1046f16)) by [@L-1124](https://github.com/L-1124) in [#56](https://github.com/L-1124/QQMusicApi/pull/56)
* 支持获取 OGG 320kbps ([7d66486](https://github.com/L-1124/QQMusicApi/commit/7d66486379e8009a60514806d1373f51840010be)) by [@L-1124](https://github.com/L-1124) in [#55](https://github.com/L-1124/QQMusicApi/pull/55)
* 支持获取加密和试听文件 ([bb6cf81](https://github.com/L-1124/QQMusicApi/commit/bb6cf816a4bb79c5b846e211f4a216b5764dc4de)) by [@L-1124](https://github.com/L-1124) in [#51](https://github.com/L-1124/QQMusicApi/pull/51)

### 文档更新

* 简化贡献文档 ([3bae431](https://github.com/L-1124/QQMusicApi/commit/3bae4311368f557d3f83e1b34a9efbe84c43b046)) by [@L-1124](https://github.com/L-1124) in [#54](https://github.com/L-1124/QQMusicApi/pull/54)

### 贡献者

* @L-1124 [#57](https://github.com/L-1124/QQMusicApi/pull/57)

## [[0.1.6](https://github.com/L-1124/QQMusicApi/compare/v0.1.5..v0.1.6)] - 2024-08-25

### Bug 修复

* 注释错误 ([0afd820](https://github.com/L-1124/QQMusicApi/commit/0afd820776e117a0d15c282ec8c258c49d0a48e3)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* 迁移到 httpx ([99fb2d9](https://github.com/L-1124/QQMusicApi/commit/99fb2d9e4a1468da49f155beb4d08d43e99abccb)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* 重构 Api 代码 ([9e63a1e](https://github.com/L-1124/QQMusicApi/commit/9e63a1eb4a8cc01a235545c669881b92bafe5868)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 优化贡献文档 ([68c23c3](https://github.com/L-1124/QQMusicApi/commit/68c23c32dd98596f67bdc91aeea12892680aa49c)) by [@L-1124](https://github.com/L-1124)
* 更新贡献指南 ([d04053b](https://github.com/L-1124/QQMusicApi/commit/d04053b13d1776054429f5477a6be3aadeef1d16)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124 [#48](https://github.com/L-1124/QQMusicApi/pull/48)

## [[0.1.5](https://github.com/L-1124/QQMusicApi/compare/v0.1.4..v0.1.5)] - 2024-08-03

### Bug 修复

* 未使用上下文管理器时报错 ([bc647fa](https://github.com/L-1124/QQMusicApi/commit/bc647fa9a033bf6f661fb633611293f8c84e40c9)) by [@L-1124](https://github.com/L-1124)
* 修复一些小错误 ([1fc449a](https://github.com/L-1124/QQMusicApi/commit/1fc449a8c228a8dcc166efd35b84670550c6c2e4)) by [@L-1124](https://github.com/L-1124)
* v0.1.4 未包含库文件 ([7963f54](https://github.com/L-1124/QQMusicApi/commit/7963f547fbfa5bcdcd90c4776d9f1776211f41fa)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* 增加对 albumId 的支持 ([d81de7f](https://github.com/L-1124/QQMusicApi/commit/d81de7f532940ef3e802d36e3341d1b98d1bc63d)) by [@L-1124](https://github.com/L-1124)

### 文档更新

* 更新 readme ([a454e21](https://github.com/L-1124/QQMusicApi/commit/a454e21183277e0ebf7420cbee76bd549c73c7f0)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124

## [[0.1.4](https://github.com/L-1124/QQMusicApi/compare/v0.1.3..v0.1.4)] - 2024-07-28

### 构建配置

* 更新 pyproject.toml ([aad543b](https://github.com/L-1124/QQMusicApi/commit/aad543b58fe73f46d0eaf6f552dd9a82ad7ca0c5)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124 [#41](https://github.com/L-1124/QQMusicApi/pull/41)

## [[0.1.3](https://github.com/L-1124/QQMusicApi/compare/v0.1.2..v0.1.3)] - 2024-07-27

### 文档更新

* 更完善的 API 文档 ([2f62297](https://github.com/L-1124/QQMusicApi/commit/2f62297e19de86e5c6ee7f88f0a58efe74cd2d47)) by [@L-1124](https://github.com/L-1124) in [#38](https://github.com/L-1124/QQMusicApi/pull/38)

### 构建配置

* 迁移依赖管理工具为 PDM ([9262b5c](https://github.com/L-1124/QQMusicApi/commit/9262b5c65ec757329fd729308da28bf47e059951)) by [@L-1124](https://github.com/L-1124) in [#35](https://github.com/L-1124/QQMusicApi/pull/35)

### 贡献者

* @L-1124

## [[0.1.2](https://github.com/L-1124/QQMusicApi/compare/v0.1.1..v0.1.2)] - 2024-07-21

### Bug 修复

* 部分类型错误 ([f188f6e](https://github.com/L-1124/QQMusicApi/commit/f188f6ef7e034cc3dfef73dd6ab84ad684393fd3)) by [@L-1124](https://github.com/L-1124)
* Fatal error on SSL transport ([81a00c7](https://github.com/L-1124/QQMusicApi/commit/81a00c74893b23946d46bcb5854b46f15c3ebd8f)) by [@L-1124](https://github.com/L-1124)
* python3.9 union syntax ([4475513](https://github.com/L-1124/QQMusicApi/commit/4475513e9849619bb347d3aa776d45cd831707ac)) by [@L-1124](https://github.com/L-1124)
* `Api`传入`Credential`无效 ([eb1fe62](https://github.com/L-1124/QQMusicApi/commit/eb1fe620afa25d68590002c5311eb368a92ca255)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(login)** 添加报错信息，优化二维码获取 ([721546f](https://github.com/L-1124/QQMusicApi/commit/721546f45022edd819fab11c773962cf1db9c0a8)) by [@L-1124](https://github.com/L-1124)
* 更好的错误输出 ([05ea8fe](https://github.com/L-1124/QQMusicApi/commit/05ea8fec7e780195b89d6354af3bb714d1ebb07a)) by [@L-1124](https://github.com/L-1124)
* 懒获取QIMEI36 ([218a740](https://github.com/L-1124/QQMusicApi/commit/218a740136cef98082e840c75a3c4393c2caa0be)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* 重构 `LoginApi` 代码 ([a44d5ab](https://github.com/L-1124/QQMusicApi/commit/a44d5ab35c846aa9483bfa76e94838e78fba4fbb)) by [@L-1124](https://github.com/L-1124) in [#33](https://github.com/L-1124/QQMusicApi/pull/33)
* 重构代码 ([9b17bf6](https://github.com/L-1124/QQMusicApi/commit/9b17bf626094376dbfa314c5ac095db396a1e5a7)) by [@L-1124](https://github.com/L-1124) in [#22](https://github.com/L-1124/QQMusicApi/pull/22)

### 性能优化

* 优化 LoginApi ([bcdae55](https://github.com/L-1124/QQMusicApi/commit/bcdae55e61fb7ee52db03643f235fc6a165e0e27)) by [@L-1124](https://github.com/L-1124)
* 优化 TopApi ([46a1965](https://github.com/L-1124/QQMusicApi/commit/46a196566641d199d12fd2540d0d8575fc9ebf41)) by [@L-1124](https://github.com/L-1124)

### 构建配置

* 移除不必要的开发依赖 ([3d1dd29](https://github.com/L-1124/QQMusicApi/commit/3d1dd292e87dd17c5be4e95d5d50ca23b60e40b7)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124 [#34](https://github.com/L-1124/QQMusicApi/pull/34)

## [[0.1.1](https://github.com/L-1124/QQMusicApi/compare/v0.1.0..v0.1.1)] - 2024-07-14

### Bug 修复

* 修改错误注释 ([1a36d71](https://github.com/L-1124/QQMusicApi/commit/1a36d7138c9f21fe13d08e4731922cc68e454cdc)) by [@L-1124](https://github.com/L-1124) in [#21](https://github.com/L-1124/QQMusicApi/pull/21)
* import issue ([cd72cd7](https://github.com/L-1124/QQMusicApi/commit/cd72cd7809d371b2b17117c4c78d8eb31a3327cb)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* **(SingerApi)** 添加 SingerApi Api ([506faaa](https://github.com/L-1124/QQMusicApi/commit/506faaa60f7ec1336dc2532dc4dc2006ed167990)) by [@L-1124](https://github.com/L-1124)
* **(SongApi)** 歌曲Api支持传入Credential ([07e7a09](https://github.com/L-1124/QQMusicApi/commit/07e7a0994ac320d0892f94a6da386684d5c5c7a7)) by [@L-1124](https://github.com/L-1124)
* **(SongApi)** 增加获取 Album, Singer ([606a163](https://github.com/L-1124/QQMusicApi/commit/606a1632a6521c34e50c6631f0a0b6de9d292eb8)) by [@L-1124](https://github.com/L-1124)
* Singer API ([b137846](https://github.com/L-1124/QQMusicApi/commit/b137846ed87d43e15e9078b90203b4e03126d423)) by [@L-1124](https://github.com/L-1124) in [#13](https://github.com/L-1124/QQMusicApi/pull/13)
* 支持 `__repr__` 和 `__str__` ([7959f85](https://github.com/L-1124/QQMusicApi/commit/7959f85b388e8b3150b2123a229ffa8b6aff6730)) by [@L-1124](https://github.com/L-1124)
* 增加获取歌手列表 API ([ae00447](https://github.com/L-1124/QQMusicApi/commit/ae00447e00aec2615781f06a6b421e2e4db77aba)) by [@L-1124](https://github.com/L-1124)
* add Singer API data ([dd641e5](https://github.com/L-1124/QQMusicApi/commit/dd641e5b010cb309875903d6ebe7c3aed8d82926)) by [@L-1124](https://github.com/L-1124)

### 性能优化

* 优化获取多个歌曲播放链接性能 ([2168c07](https://github.com/L-1124/QQMusicApi/commit/2168c0795b3f1d2a6ac9b83fbfb11239bdb0241b)) by [@L-1124](https://github.com/L-1124) in [#14](https://github.com/L-1124/QQMusicApi/pull/14)

### 文档更新

* update readme ([203c264](https://github.com/L-1124/QQMusicApi/commit/203c2648b5510d103a58d6a9857b4d392aa2f97f)) by [@L-1124](https://github.com/L-1124)
* 添加 API 文档 ([b2d2a8e](https://github.com/L-1124/QQMusicApi/commit/b2d2a8eecd2a763ca27d94aa222526b7d08c2a8b)) by [@L-1124](https://github.com/L-1124)
* 更新 TODO ([5b72d8d](https://github.com/L-1124/QQMusicApi/commit/5b72d8da90401644e0224b9c1d9a6dd08eec0c57)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124 [#21](https://github.com/L-1124/QQMusicApi/pull/21)

## [0.1.0] - 2024-06-07

### Init

* 初始化 main 分支 ([352c814](https://github.com/L-1124/QQMusicApi/commit/352c814a79d0ae64714a5d0bcddc353f36ab1b44)) by [@L-1124](https://github.com/L-1124)

### 功能更新

* add Top API ([6785b4b](https://github.com/L-1124/QQMusicApi/commit/6785b4b2bc0a729f3291c7b50d6fa35726b6dac2)) by [@L-1124](https://github.com/L-1124)
* add MV API ([016f40b](https://github.com/L-1124/QQMusicApi/commit/016f40b5b3c3f355128275045332cfb9ec0cc864)) by [@L-1124](https://github.com/L-1124)
* add Album API ([e827510](https://github.com/L-1124/QQMusicApi/commit/e827510dc8e3ce2931a90006243dd735adbefefd)) by [@L-1124](https://github.com/L-1124)
* add Songlist API ([5c9b045](https://github.com/L-1124/QQMusicApi/commit/5c9b04558ea3f32037cec62a019f0c4081796b9d)) by [@L-1124](https://github.com/L-1124)
* add Login API ([480656e](https://github.com/L-1124/QQMusicApi/commit/480656e06911267c2ce6f61c5a7f8bb647813e78)) by [@L-1124](https://github.com/L-1124)
* add Song API ([6be6382](https://github.com/L-1124/QQMusicApi/commit/6be638203adc2bc86b6e4b525a4011997174b4f3)) by [@L-1124](https://github.com/L-1124)
* add Search API ([7e71614](https://github.com/L-1124/QQMusicApi/commit/7e71614367995c8e69fa51bdb396f9ae9937ac1f)) by [@L-1124](https://github.com/L-1124)

### 功能重构

* some functions directly return Class Song ([40e2c11](https://github.com/L-1124/QQMusicApi/commit/40e2c11d6f18a73276e2bb675b6a9baabc2f0999)) by [@L-1124](https://github.com/L-1124)

### 构建配置

* update pyproject.toml ([6320fdb](https://github.com/L-1124/QQMusicApi/commit/6320fdbf491f926eb9ce673c5349b8638d64ee75)) by [@L-1124](https://github.com/L-1124)

### 贡献者

* @L-1124
