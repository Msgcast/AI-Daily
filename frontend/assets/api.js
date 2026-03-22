/**
 * Shared API client and utilities
 */

const API_BASE = "";  // same origin

// ─── HTTP helpers ─────────────────────────────────────────────

export async function apiFetch(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

export const api = {
    // Records
    getStats:     ()       => apiFetch("/api/records/stats"),
    getRecords:   (p=1)    => apiFetch(`/api/records?page=${p}&page_size=20`),
    getRecord:    (id)     => apiFetch(`/api/records/${id}`),

    // Run
    runNews:      ()       => apiFetch("/api/run/news", { method: "POST", body: JSON.stringify({}) }),
    runReddit:    ()       => apiFetch("/api/run/reddit", { method: "POST" }),
    getRunStatus: (tid)    => apiFetch(`/api/run/status/${tid}`),

    // Schedule
    getJobs:      ()       => apiFetch("/api/schedule"),
    createJob:    (data)   => apiFetch("/api/schedule", { method: "POST", body: JSON.stringify(data) }),
    deleteJob:    (jid)    => apiFetch(`/api/schedule/${jid}`, { method: "DELETE" }),
    toggleJob:    (jid)    => apiFetch(`/api/schedule/${jid}/toggle`, { method: "POST" }),

    // Sources
    getSources:   ()       => apiFetch("/api/sources"),
    createSource: (data)   => apiFetch("/api/sources", { method: "POST", body: JSON.stringify(data) }),
    updateSource: (id,data)=> apiFetch(`/api/sources/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    deleteSource: (id)     => apiFetch(`/api/sources/${id}`, { method: "DELETE" }),
    validateSource:(id)    => apiFetch(`/api/sources/${id}/validate`, { method: "POST" }),

    // External
    getDeepSeekBalance: () => apiFetch("/api/external/deepseek/balance"),
    getXHSStatus:       () => apiFetch("/api/external/xhs/login_status"),
};

// ─── SSE Log Stream ───────────────────────────────────────────

export function streamLog(taskId, onLine, onDone) {
    const es = new EventSource(`/api/run/log/${taskId}`);
    es.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.event === "done") {
            es.close();
            onDone?.();
        } else if (data.log) {
            onLine(data.log);
        }
    };
    es.onerror = () => { es.close(); onDone?.(); };
    return es;
}

// ─── Three.js WebGL Background ───────────────────────────────

export function initWebGL(containerId) {
    if (!window.THREE) return;
    const container = document.getElementById(containerId);
    if (!container) return;

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
    camera.position.z = 1;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const geometry = new THREE.PlaneGeometry(2, 2);

    const vertexShader = `
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = vec4(position, 1.0); }
    `;
    const fragmentShader = `
        uniform float u_time; uniform vec2 u_resolution; uniform vec2 u_mouse;
        uniform vec3 u_colorCore; uniform vec3 u_colorFringe; uniform float u_isLightMode;
        varying vec2 vUv;
        vec2 hash(vec2 p) {
            p = vec2(dot(p,vec2(127.1,311.7)), dot(p,vec2(269.5,183.3)));
            return -1.0 + 2.0*fract(sin(p)*43758.5453123);
        }
        float noise(in vec2 p) {
            const float K1=0.366025404; const float K2=0.211324865;
            vec2 i=floor(p+(p.x+p.y)*K1); vec2 a=p-i+(i.x+i.y)*K2;
            vec2 o=(a.x>a.y)?vec2(1.0,0.0):vec2(0.0,1.0);
            vec2 b=a-o+K2; vec2 c=a-1.0+2.0*K2;
            vec3 h=max(0.5-vec3(dot(a,a),dot(b,b),dot(c,c)),0.0);
            vec3 n=h*h*h*h*vec3(dot(a,hash(i+0.0)),dot(b,hash(i+o)),dot(c,hash(i+1.0)));
            return dot(n,vec3(70.0));
        }
        float sdArc(vec2 p, vec2 center, float radius, float width, float warp) {
            p.y += sin(p.x*2.5+u_time*0.3)*warp;
            p.x += noise(p*1.5+u_time*0.1)*(warp*0.4);
            float d = length(p-center)-radius;
            return abs(d)-width;
        }
        void main() {
            vec2 uv=gl_FragCoord.xy/u_resolution.xy; vec2 st=uv;
            st.x *= u_resolution.x/u_resolution.y;
            vec2 mouseOffset=(u_mouse-0.5)*0.15; st+=mouseOffset;
            vec2 center=vec2(0.1,0.5);
            float d1=sdArc(st,center,0.9,0.005,0.08);
            float d2=sdArc(st,center,0.92,0.03,0.12);
            float coreGlow=exp(-d1*45.0); float fringeGlow=exp(-d2*12.0);
            float wash=smoothstep(0.8,-0.3,st.x)*0.2;
            vec3 finalColor=u_colorCore*coreGlow+u_colorFringe*fringeGlow+u_colorFringe*wash;
            float alpha=clamp(coreGlow+fringeGlow+wash,0.0,1.0);
            if(u_isLightMode>0.5) alpha=clamp((coreGlow*0.8+fringeGlow*0.4+wash*0.3),0.0,0.4);
            gl_FragColor=vec4(finalColor,alpha);
        }
    `;

    function getColors() {
        const s = getComputedStyle(document.documentElement);
        return {
            core:   new THREE.Color(s.getPropertyValue("--shader-core").trim()),
            fringe: new THREE.Color(s.getPropertyValue("--shader-fringe").trim()),
        };
    }

    const initialTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const colors = getColors();
    const material = new THREE.ShaderMaterial({
        vertexShader, fragmentShader,
        uniforms: {
            u_time:        { value: 0 },
            u_resolution:  { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
            u_mouse:       { value: new THREE.Vector2(0.5, 0.5) },
            u_colorCore:   { value: colors.core },
            u_colorFringe: { value: colors.fringe },
            u_isLightMode: { value: initialTheme === "light" ? 1.0 : 0.0 },
        },
        transparent: true,
        blending: THREE.NormalBlending,
    });

    scene.add(new THREE.Mesh(geometry, material));

    let targetMouse = new THREE.Vector2(0.5, 0.5);
    document.addEventListener("mousemove", (e) => {
        targetMouse.x = e.clientX / window.innerWidth;
        targetMouse.y = 1.0 - e.clientY / window.innerHeight;
    });

    const clock = new THREE.Clock();
    (function animate() {
        requestAnimationFrame(animate);
        material.uniforms.u_time.value = clock.getElapsedTime();
        material.uniforms.u_mouse.value.lerp(targetMouse, 0.05);
        renderer.render(scene, camera);
    })();

    window.addEventListener("resize", () => {
        renderer.setSize(window.innerWidth, window.innerHeight);
        material.uniforms.u_resolution.value.set(window.innerWidth, window.innerHeight);
    });

    return { material, getColors };
}

// ─── Theme toggle helper ──────────────────────────────────────

export function initTheme(btnId, { onThemeChange } = {}) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    const html = document.documentElement;
    const saved = localStorage.getItem("theme") || "dark";
    html.setAttribute("data-theme", saved);
    _updateThemeBtn(btn, saved);

    btn.addEventListener("click", () => {
        const next = html.getAttribute("data-theme") === "dark" ? "light" : "dark";
        html.setAttribute("data-theme", next);
        localStorage.setItem("theme", next);
        _updateThemeBtn(btn, next);
        onThemeChange?.(next);
    });
}

function _updateThemeBtn(btn, theme) {
    const icon = btn.querySelector("i");
    const text = btn.querySelector("span");
    if (icon) icon.className = theme === "dark" ? "ph ph-moon" : "ph ph-sun";
    if (text) text.textContent = theme === "dark" ? "DARK" : "LIGHT";
}

// ─── Toast ────────────────────────────────────────────────────

export function toast(msg, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }
    const el = document.createElement("div");
    el.className = "toast";
    const icons = { success: "ph-check-circle", error: "ph-x-circle", info: "ph-info", warning: "ph-warning" };
    el.innerHTML = `<i class="ph ${icons[type] || "ph-info"}"></i> ${msg}`;
    container.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

// ─── Helpers ──────────────────────────────────────────────────

export function fmtDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

export function statusBadge(status) {
    const map = {
        success: ["badge-success", "✓ 成功"],
        failed:  ["badge-error",   "✗ 失败"],
        running: ["badge-running", "⟳ 运行中"],
        pending: ["",              "● 等待中"],
    };
    const [cls, label] = map[status] || ["", status];
    return `<span class="badge ${cls}">${label}</span>`;
}
