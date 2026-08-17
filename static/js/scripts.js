document.addEventListener("DOMContentLoaded", () => {
    // ===============================
    // Theme Toggle (Claro / Escuro)
    // ===============================
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon   = document.getElementById('theme-icon');
    const html        = document.documentElement;

    function applyTheme(theme) {
        html.setAttribute('data-theme', theme);
        try { localStorage.setItem('cinnamon-theme', theme); } catch(e) {}
        if (themeIcon) {
            themeIcon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
        }
        if (themeToggle) {
            themeToggle.title = theme === 'dark' ? 'Mudar para modo claro' : 'Mudar para modo escuro';
        }
        document.dispatchEvent(new CustomEvent('cinnamon:theme-changed', { detail: { theme: theme } }));
    }

    // Inicializa ícone conforme tema atual (já aplicado pelo script inline no <head>)
    const currentTheme = html.getAttribute('data-theme') || 'light';
    applyTheme(currentTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', function () {
            const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(next);
        });
    }

    // ===============================
    // Navbar mobile: troca o ícone do hambúrguer (≡ / ✕) conforme abre/fecha
    // ===============================
    const navToggle = document.querySelector('.site-nav__toggle');
    const navMenu = document.getElementById('navbarNav');
    if (navToggle && navMenu) {
        const navToggleIcon = navToggle.querySelector('i');
        navMenu.addEventListener('shown.bs.collapse', function () {
            if (navToggleIcon) navToggleIcon.className = 'bi bi-x-lg';
        });
        navMenu.addEventListener('hidden.bs.collapse', function () {
            if (navToggleIcon) navToggleIcon.className = 'bi bi-list';
        });
    }
});
