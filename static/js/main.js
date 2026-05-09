/* ════════════════════════════════════════════
   CertVerify – main.js
════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

  // --- Theme Toggle ---
  const themeToggle = document.getElementById('themeToggle');
  const themeIcon = document.getElementById('themeIcon');
  const htmlEl = document.documentElement;

  if (themeToggle) {
    // Check saved theme
    const savedTheme = localStorage.getItem('certverify-theme') || 'light';
    htmlEl.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    // Toggle on click
    themeToggle.addEventListener('click', () => {
      const currentTheme = htmlEl.getAttribute('data-theme');
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      
      htmlEl.setAttribute('data-theme', newTheme);
      localStorage.setItem('certverify-theme', newTheme);
      updateThemeIcon(newTheme);
    });
  }

  function updateThemeIcon(theme) {
    if (!themeIcon) return;
    if (theme === 'dark') {
      themeIcon.className = 'bi bi-sun-fill text-warning';
    } else {
      themeIcon.className = 'bi bi-moon-stars-fill text-white';
    }
  }

  // --- Auto-Hide Toasts after 5 seconds ---
  const toasts = document.querySelectorAll('.toast');
  toasts.forEach(toastEl => {
    setTimeout(() => {
      const bsToast = new bootstrap.Toast(toastEl);
      bsToast.hide();
    }, 5000);
  });

});
