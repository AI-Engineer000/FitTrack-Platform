document.addEventListener("DOMContentLoaded", function () {

    const sidebar = document.getElementById("sidebar");
    const menuToggle = document.getElementById("menuToggle");
    const overlay = document.getElementById("sidebarOverlay");

    if (!sidebar || !menuToggle) return;

    // Initialize aria state
    menuToggle.setAttribute('aria-expanded', sidebar.classList.contains('collapsed') ? 'false' : 'true');

    // Toggle sidebar on hamburger click
    menuToggle.addEventListener("click", function () {
        if (window.innerWidth > 768) {
            // Desktop: collapse/expand sidebar
            sidebar.classList.toggle("collapsed");
            menuToggle.classList.toggle("active");
            // ensure overlay is hidden on desktop
            if (overlay) overlay.classList.remove("active");
            // update aria
            const expanded = !sidebar.classList.contains('collapsed');
            menuToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        } else {
            // Mobile: slide-in sidebar with overlay
            sidebar.classList.toggle("open");
            menuToggle.classList.toggle("active");
            if (overlay) overlay.classList.toggle("active");
            menuToggle.setAttribute('aria-expanded', sidebar.classList.contains('open') ? 'true' : 'false');
        }
    });

    // Close sidebar when overlay is clicked (mobile)
    if (overlay) {
        overlay.addEventListener("click", function () {
            sidebar.classList.remove("open");
            menuToggle.classList.remove("active");
            overlay.classList.remove("active");
            menuToggle.setAttribute('aria-expanded', 'false');
        });
    }

    // Close sidebar when nav link clicked (mobile)
    sidebar.querySelectorAll(".nav-item").forEach(function (link) {
        link.addEventListener("click", function () {
            if (window.innerWidth <= 768) {
                sidebar.classList.remove("open");
                menuToggle.classList.remove("active");
                if (overlay) overlay.classList.remove("active");
                menuToggle.setAttribute('aria-expanded', 'false');
            }
        });
    });

    // Keep aria state in sync on window resize
    window.addEventListener('resize', function () {
        if (window.innerWidth > 768) {
            // on desktop ensure overlay is hidden
            if (overlay) overlay.classList.remove('active');
            // set aria-expanded according to collapsed state
            const expanded = !sidebar.classList.contains('collapsed');
            menuToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        } else {
            // on mobile, reflect open state
            menuToggle.setAttribute('aria-expanded', sidebar.classList.contains('open') ? 'true' : 'false');
        }
    });

    // Expose a simple global toggle function as a fallback for inline onclick
    window.toggleSidebar = function () {
        if (window.innerWidth > 768) {
            sidebar.classList.toggle('collapsed');
            menuToggle.classList.toggle('active');
            if (overlay) overlay.classList.remove('active');
            const expanded = !sidebar.classList.contains('collapsed');
            menuToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        } else {
            sidebar.classList.toggle('open');
            menuToggle.classList.toggle('active');
            if (overlay) overlay.classList.toggle('active');
            menuToggle.setAttribute('aria-expanded', sidebar.classList.contains('open') ? 'true' : 'false');
        }
    };

});