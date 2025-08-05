document.addEventListener("DOMContentLoaded", () => {
  const playlist = document.getElementById("playlist");
  const audio = document.getElementById("main-audio");
  const source = document.getElementById("audio-source");

  playlist.querySelectorAll("li").forEach(item => {
    item.addEventListener("click", () => {
      // Remove active from all
      playlist.querySelectorAll("li").forEach(li => li.classList.remove("active"));
      
      // Set this as active
      item.classList.add("active");

      // Load new song
      const newSrc = item.getAttribute("data-src");
      source.src = newSrc;
      audio.load();
      audio.play();
    });
  });
});