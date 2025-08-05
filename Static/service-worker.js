self.addEventListener("install", e => {
  e.waitUntil(
    caches.open("memory-app").then(cache => {
      return cache.addAll([
        "/",
        "/static/style.css",
        "/static/script.js",
        "/manifest.json",
        "/static/playlist.js",
        "/static/unlock.js",
        "/static/unlock.css",
        "/static/memory.css",
        "/static/memory1.js",
        "/static/avatar_idle.jpg",
        "/static/avatar1.jpg",
        "/static/avatar2.jpg",
        "/static/mem1.jpg",
        "/static/mem2.jpg",
        "/static/mem3.jpg",
        "/static/comic_pages/comic_1.png",
        "/static/comic_pages/comic_2.png",
        "/static/comic_pages/comic_3.png",
        "/static/comic_pages/comic_4.png",
        "/static/comic_pages/comic_5.png", 
        "/static/comic_pages/comic_6.png",
        "/static/comic_pages/comic_cover.png",
        "/static/comic_pages/comic_choice.png",
        "/static/audio/song1.mp3",
        "/static/audio/song2.mp3",
        "/static/audio/song3.mp3",
        "/static/audio/song4.mp3",
        "/static/audio/song5.mp3",
        "/static/audio/song6.mp3",  
        "/static/AD_pics/Aadhi_bg.jpg",
        "/static/AD_pics/Aadhi1.jpg",
        "/static/AD_pics/Aadhi2.jpg",
        "/static/AD_pics/Aadhi3.jpg",
        "/static/AD_pics/Aadhi4.jpg",
        "/static/AD_pics/Aadhi5.jpg",
        "/static/AD_pics/Aadhi6.jpg",
        "/static/AD_pics/Aadhi7.jpg",
        "/static/AD_pics/Aadhi8.jpg",
        "/static/AD_pics/Aadhi9.jpg",
        "/static/AD_pics/Aadhi10.jpg",
        "/static/memory_video.mp4",
        "/templates/index.html",
        "/templates/memory.html",
        "/templates/memory1.html",
        "/templates/memory2.html",
        "/templates/memory3.html",
        "/templates/memory4.html",
        "/templates/memory5.html",
        "/templates/memory6.html",
        "/templates/unlock.html",
        // Add all your other files here (html pages, images, etc.)
      ]);
    })
  );
});

self.addEventListener("fetch", e => {
  e.respondWith(
    caches.match(e.request).then(response => {
      return response || fetch(e.request);
    })
  );
});
