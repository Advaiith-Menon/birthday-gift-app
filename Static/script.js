if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/js/service-worker.js")
    .then(() => console.log("✅ Service Worker Registered"))
    .catch(err => console.error("❌ Registration failed:", err));
}
document.addEventListener("DOMContentLoaded", () => {
  // Debounce utility
  function debounce(func, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => func.apply(this, args), delay);
    };
  }

  let avatarInterval;

  function startAvatarAnimation() {
    const avatarA = document.getElementById('avatar-a');
    const avatarB = document.getElementById('avatar-b');
    const avatarStatic = document.getElementById('avatar-static');

    avatarStatic.style.display = 'none';
    avatarA.style.display = 'block';
    avatarB.style.display = 'none';

    avatarInterval = setInterval(() => {
      if (avatarA.style.display === 'block') {
        avatarA.style.display = 'none';
        avatarB.style.display = 'block';
      } else {
        avatarA.style.display = 'block';
        avatarB.style.display = 'none';
      }
    }, 400);
  }

  function stopAvatarAnimation() {
    clearInterval(avatarInterval);
    document.getElementById('avatar-a').style.display = 'none';
    document.getElementById('avatar-b').style.display = 'none';
    document.getElementById('avatar-static').style.display = 'block';
  }

  const sendMessage = debounce(async function () {
    const input = document.getElementById('user-input');
    const chatLog = document.getElementById('chat-log');
    const message = input.value.trim();

    if (!message) return;

    chatLog.innerHTML += `<div class="message user-msg">${message}</div>`;
    chatLog.scrollTop = chatLog.scrollHeight;
    input.value = '';
    input.disabled = true;

    startAvatarAnimation();

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });

      const data = await res.json();
      const reply = data.reply;

      stopAvatarAnimation();

      if (reply === "__UNLOCK__") {
        chatLog.innerHTML += `<div class="message bot">Yeah, That is true!!!</div>`;
        chatLog.scrollTop = chatLog.scrollHeight;
        setTimeout(() => {
          window.location.href = "/unlock";
        }, 1500);
      } else {
        chatLog.innerHTML += `<div class="message bot">${reply}</div>`;
        chatLog.scrollTop = chatLog.scrollHeight;
      }

    } catch (error) {
      stopAvatarAnimation();
      chatLog.innerHTML += `<div class="message bot error">❌ Oops! I don't remember that!!!</div>`;
      console.error("Chat error:", error);
    }

    input.disabled = false;
    input.focus();
  }, 400);

  // Submit on Enter key
  document.getElementById("user-input").addEventListener("keypress", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });

  // Hook for button (optional fallback)
  window.sendMessage = sendMessage;
});
