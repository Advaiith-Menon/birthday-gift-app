
function launchConfetti() {
  const duration = 6 * 1000;
  const animationEnd = Date.now() + duration;
  const defaults = { startVelocity: 30, spread: 360, ticks: 70, zIndex: 100 };

  function randomInRange(min, max) {
    return Math.random() * (max - min) + min;
  }

  const interval = setInterval(function () {
    const timeLeft = animationEnd - Date.now();
    if (timeLeft <= 0) {
      return clearInterval(interval);
    }

    confetti(Object.assign({}, defaults, {
      particleCount: 400,
      origin: {
        x: randomInRange(0.1, 0.3),
        y: Math.random() - 0.2
      }
    }));

    confetti(Object.assign({}, defaults, {
      particleCount: 50,
      origin: {
        x: randomInRange(0.7, 0.9),
        y: Math.random() - 0.2
      }
    }));
  }, 1000);
}
function startCountdown() {
    launchConfetti()
      const countdown = document.getElementById("countdownWrapper");
      countdown.style.display = "block";
      let counter = 5;
      countdown.textContent = counter;

      const interval = setInterval(() => {
        counter--;
        countdown.textContent = counter;
        if (counter === 0) {
          clearInterval(interval);
          window.location.href = "/memory"; // Redirect to memory page
        }
      }, 1000);}