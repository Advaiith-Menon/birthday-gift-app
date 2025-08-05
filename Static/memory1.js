window.addEventListener("load", () => {
  const container = document.querySelector(".container");
  const miniHearts = document.querySelectorAll(".mini-heart");

  const placeHearts = () => {
    const centerX = container.offsetWidth / 2;
    const centerY = container.offsetHeight / 2;
    const radius = 200;

    miniHearts.forEach((heart, index) => {
      const angle = (index / miniHearts.length) * (2 * Math.PI);
      const heartWidth = heart.offsetWidth;
      const heartHeight = heart.offsetHeight;

      const x = centerX + radius * Math.cos(angle) - heartWidth / 2;
      const y = centerY + radius * Math.sin(angle) - heartHeight / 2;

      heart.style.left = `${x}px`;
      heart.style.top = `${y}px`;
    });
  };

  // Delay until next animation frame (ensures layout is complete)
  requestAnimationFrame(placeHearts);
});
// Generate stars
for (let i = 0; i < 100; i++) {
    const star = document.createElement('div');
    star.className = 'star';
    star.style.top = `${Math.random() * 100}vh`;
    star.style.left = `${Math.random() * 100}vw`;
    star.style.animationDelay = `${Math.random() * 3}s`;
    document.body.appendChild(star);
}