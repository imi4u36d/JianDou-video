<template>
  <header class="app-header">
    <div class="header-brand">
      <h1>剪豆视频</h1>
    </div>
    <nav class="header-nav">
      <router-link to="/">首页</router-link>
      <router-link to="/generate">生成</router-link>
      <router-link to="/queue">队列</router-link>
      <router-link to="/gallery">作品</router-link>
      <router-link to="/models">模型</router-link>
      <router-link to="/settings">设置</router-link>
    </nav>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #1a1a2e;
  color: #eee;
  border-bottom: 1px solid #2a2a3e;
}
.header-brand h1 {
  font-size: 18px;
  margin: 0;
  background: linear-gradient(135deg, #e94560, #0f3460);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-nav {
  display: flex;
  gap: 16px;
}
.header-nav a {
  color: #aaa;
  text-decoration: none;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
}
.header-nav a:hover,
.header-nav a.router-link-active {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}
</style>
