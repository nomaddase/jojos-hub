# Jojo's UI (React + Vite)

UI for kiosk, kitchen, and display surfaces. This app intentionally stays with a lean stack:

- React (JSX) + CSS for production-specific interfaces
- No heavy generic UI frameworks (for example Material UI or Ant Design)
- Small focused libraries are allowed only when they clearly improve UX
  - animations/transitions: `framer-motion`
  - icons: `lucide-react`
  - lightweight primitives: only if truly required

## Why this approach

The local core service is not the primary bottleneck. We optimize for client stability and responsiveness on kiosk/WebView devices by:

- keeping bundles small
- minimizing runtime complexity
- favoring custom task-focused interfaces over generic business UI kits
