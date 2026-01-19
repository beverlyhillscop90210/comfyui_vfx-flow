import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";
import { api } from "../../scripts/api.js";

const VFX_FLOW_NODES = [
    "FlowLogin",
    "ProjectBrowser",
    "ShotBrowser",
    "TaskSelector",
    "PublishToFlow",
    "FilenameFromFlow",
    "AddNote"
];

const FLOW_COLOR = "#1a4a4a";
const FLOW_COLOR_DARK = "#0d2d2d";
const FLOW_COLOR_SUCCESS = "#1a5a3a";
const WATERMARK = "rgba(255,255,255,0.06)";

function maskPasswordWidget(widget) {
    if (!widget || !widget.inputEl) return;
    widget.inputEl.type = "password";
    widget.inputEl.style.letterSpacing = "2px";
}

app.registerExtension({
    name: "vfx.flow.style",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (!VFX_FLOW_NODES.includes(nodeData.name)) return;
        
        if (nodeData.name === "FlowLogin") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated?.apply(this, []);
                
                const node = this;
                node.loginStatus = { loggedIn: false, userName: "" };
                
                setTimeout(() => {
                    for (const widget of node.widgets || []) {
                        if (widget.name === "password" || widget.name === "api_key") {
                            maskPasswordWidget(widget);
                        }
                    }
                }, 100);
                
                // Add Login Button
                const btnWidget = this.addWidget("button", "login_btn", "Login", async () => {
                    const getVal = (n) => node.widgets?.find(w => w.name === n)?.value || "";
                    
                    btnWidget.name = "Connecting...";
                    node.setDirtyCanvas(true);
                    
                    try {
                        const resp = await api.fetchApi("/vfx-flow/login", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                site_url: getVal("site_url"),
                                auth_method: getVal("auth_method"),
                                login: getVal("login"),
                                password: getVal("password"),
                                script_name: getVal("script_name"),
                                api_key: getVal("api_key")
                            })
                        });
                        
                        const result = await resp.json();
                        
                        if (result.success) {
                            node.loginStatus = { loggedIn: true, userName: result.user_name };
                            node.bgcolor = FLOW_COLOR_SUCCESS;
                            btnWidget.name = "✓ " + result.user_name;
                            if (node.statusWidget) {
                                node.statusWidget.value = "Connected to " + result.site_url;
                            }
                        } else {
                            node.loginStatus = { loggedIn: false, userName: "" };
                            node.bgcolor = FLOW_COLOR_DARK;
                            btnWidget.name = "Login";
                            alert("Login failed: " + (result.error || "Unknown error"));
                        }
                    } catch (err) {
                        node.loginStatus = { loggedIn: false, userName: "" };
                        btnWidget.name = "Login";
                        alert("Connection error: " + err.message);
                    }
                    
                    node.setDirtyCanvas(true);
                });
                
                // Status display
                this.statusWidget = ComfyWidgets["STRING"](this, "status_display", ["STRING", { multiline: true }], app).widget;
                this.statusWidget.inputEl.readOnly = true;
                this.statusWidget.inputEl.style.opacity = 0.8;
                this.statusWidget.inputEl.style.fontSize = "11px";
                this.statusWidget.inputEl.style.minHeight = "40px";
                this.statusWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
            
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                onExecuted?.apply(this, [message]);
                
                if (message?.status) {
                    const status = Array.isArray(message.status) ? message.status[0] : message.status;
                    if (this.statusWidget) {
                        this.statusWidget.value = status;
                    }
                    if (status.includes("Connected")) {
                        this.loginStatus = { loggedIn: true, userName: "Connected" };
                        this.bgcolor = FLOW_COLOR_SUCCESS;
                        const btn = this.widgets?.find(w => w.name === "login_btn" || w.type === "button");
                        if (btn) btn.name = "✓ Connected";
                    }
                }
                this.setDirtyCanvas(true);
            };
        }
        else if (["ProjectBrowser", "ShotBrowser", "TaskSelector", "PublishToFlow", "AddNote"].includes(nodeData.name)) {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated?.apply(this, []);
                
                this.infoWidget = ComfyWidgets["STRING"](this, "info_display", ["STRING", { multiline: true }], app).widget;
                this.infoWidget.inputEl.readOnly = true;
                this.infoWidget.inputEl.style.opacity = 0.8;
                this.infoWidget.inputEl.style.fontSize = "11px";
                this.infoWidget.inputEl.style.minHeight = "60px";
                this.infoWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
            
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                onExecuted?.apply(this, [message]);
                
                if (message) {
                    const info = message.info || message.status || message.text;
                    if (info && this.infoWidget) {
                        this.infoWidget.value = Array.isArray(info) ? info[0] : info;
                    }
                }
            };
        } else {
            const origCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                origCreated?.apply(this, arguments);
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        
        const origDraw = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function(ctx) {
            origDraw?.apply(this, arguments);
            ctx.save();
            ctx.font = "7px monospace";
            ctx.fillStyle = WATERMARK;
            ctx.textAlign = "right";
            ctx.fillText("vfx-flow", this.size[0] - 5, this.size[1] - 3);
            ctx.restore();
        };
    },
    
    async setup() {
        console.log("[VFX Flow] Styling loaded");
    }
});
