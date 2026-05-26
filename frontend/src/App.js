import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { api } from "./api";
export default function App() {
    const [state, setState] = useState(null);
    const refresh = async () => setState(await api.getState());
    useEffect(() => { refresh().catch(() => setState(null)); }, []);
    if (!state) {
        return (_jsx("div", { style: { padding: 24 }, children: _jsx("button", { className: "btn", onClick: async () => { await api.resetGame(); await refresh(); }, children: "\uC0C8 \uAC8C\uC784 \uC2DC\uC791" }) }));
    }
    return (_jsxs("div", { className: "app", children: [_jsxs("div", { className: "side", children: [_jsx("h3", { children: "\uD50C\uB808\uC774\uC5B4" }), _jsxs("p", { children: ["\uAE08\uD654: ", state.player.gold] }), _jsxs("p", { children: ["\uD3C9\uD310: ", state.player.reputation] }), _jsxs("p", { children: ["Phase: ", state.player.current_phase] }), _jsx("button", { className: "btn", onClick: async () => { await api.resetGame(); await refresh(); }, children: "\uC0C8 \uAC8C\uC784" })] }), _jsx("div", { className: "main", children: _jsx("pre", { children: JSON.stringify(state, null, 2) }) })] }));
}
