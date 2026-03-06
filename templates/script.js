/**
 * OpenClaw 分身评估报告 — 交互逻辑
 * 
 * 功能：暗色/亮色模式切换、中英双语切换、侧边栏导航高亮、平滑滚动
 */

(function () {
    'use strict';

    // ── 暗色模式 ────────────────────────────────
    const themeToggle = document.getElementById('themeToggle');
    const html = document.documentElement;

    function setTheme(theme) {
        html.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }

    // 初始化主题
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);

    themeToggle?.addEventListener('click', () => {
        const current = html.getAttribute('data-theme');
        setTheme(current === 'dark' ? 'light' : 'dark');
    });

    // ── 多语言切换 ──────────────────────────────
    const langBtns = document.querySelectorAll('.lang-btn');

    function setLang(lang) {
        html.setAttribute('data-lang', lang);
        localStorage.setItem('lang', lang);

        // 更新按钮状态
        langBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.lang === lang);
        });

        // 切换所有带 data-zh / data-en 的元素文本
        document.querySelectorAll('[data-zh][data-en]').forEach(el => {
            const text = el.getAttribute(lang === 'zh' ? 'data-zh' : 'data-en');
            if (text !== null) {
                el.textContent = text;
            }
        });

        // 更新页面标题
        document.title = lang === 'zh'
            ? 'OpenClaw 分身评估报告 | OpenClaw Forks Evaluation Report'
            : 'OpenClaw Forks Evaluation Report';
    }

    // 初始化语言
    const savedLang = localStorage.getItem('lang') || 'zh';
    setLang(savedLang);

    langBtns.forEach(btn => {
        btn.addEventListener('click', () => setLang(btn.dataset.lang));
    });

    // ── 侧边栏导航高亮（IntersectionObserver）───
    const tocLinks = document.querySelectorAll('.toc-link');
    const sections = document.querySelectorAll('.section[id]');

    if (sections.length && tocLinks.length) {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const id = entry.target.id;
                        tocLinks.forEach(link => {
                            link.classList.toggle(
                                'active',
                                link.getAttribute('href') === `#${id}`
                            );
                        });
                    }
                });
            },
            {
                rootMargin: '-100px 0px -60% 0px',
                threshold: 0,
            }
        );

        sections.forEach(section => observer.observe(section));
    }

    // ── 平滑滚动 ────────────────────────────────
    tocLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ── 滚动动画（懒加载区段）──────────────────
    const animateOnScroll = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.animationPlayState = 'running';
                    animateOnScroll.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.1 }
    );

    document.querySelectorAll('.section').forEach(section => {
        section.style.animationPlayState = 'paused';
        animateOnScroll.observe(section);
    });

})();
