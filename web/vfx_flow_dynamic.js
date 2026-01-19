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

// Global state for selected entities
const flowState = {
    loggedIn: false,
    userName: "",
    selectedProject: null,
    selectedSequence: null,
    selectedShot: null,
    selectedTask: null
};

function maskPasswordWidget(widget) {
    if (!widget || !widget.inputEl) return;
    widget.inputEl.type = "password";
    widget.inputEl.style.letterSpacing = "2px";
}

// Create a dropdown widget that fetches options dynamically
function createDynamicDropdown(node, name, fetchFn, onSelect) {
    const container = document.createElement("div");
    container.style.cssText = "display:flex;flex-direction:column;width:100%;";
    
    const select = document.createElement("select");
    select.style.cssText = `
        width: 100%;
        padding: 6px 10px;
        border: 1px solid #555;
        border-radius: 4px;
        background: #2a2a2a;
        color: #fff;
        font-size: 12px;
        cursor: pointer;
    `;
    select.innerHTML = '<option value="">-- Select --</option>';
    
    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "↻";
    refreshBtn.style.cssText = `
        position: absolute;
        right: 25px;
        width: 24px;
        height: 24px;
        border: none;
        background: #444;
        color: #fff;
        border-radius: 4px;
        cursor: pointer;
    `;
    
    container.appendChild(select);
    
    const widget = node.addDOMWidget(name, "select", container, {
        getValue: () => select.value,
        setValue: (v) => { select.value = v; }
    });
    
    widget.select = select;
    widget.selectedData = null;
    
    // Refresh function
    widget.refresh = async () => {
        select.innerHTML = '<option value="">Loading...</option>';
        select.disabled = true;
        
        try {
            const items = await fetchFn();
            select.innerHTML = '<option value="">-- Select --</option>';
            
            for (const item of items) {
                const opt = document.createElement("option");
                opt.value = item.id;
                opt.textContent = item.name || item.code;
                opt.dataset.item = JSON.stringify(item);
                select.appendChild(opt);
            }
        } catch (e) {
            select.innerHTML = '<option value="">Error loading</option>';
            console.error("[VFX Flow]", e);
        }
        
        select.disabled = false;
    };
    
    // On change
    select.addEventListener("change", () => {
        const opt = select.selectedOptions[0];
        if (opt && opt.dataset.item) {
            widget.selectedData = JSON.parse(opt.dataset.item);
            if (onSelect) onSelect(widget.selectedData);
        } else {
            widget.selectedData = null;
        }
        node.setDirtyCanvas(true);
    });
    
    return widget;
}

app.registerExtension({
    name: "vfx.flow.style",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (!VFX_FLOW_NODES.includes(nodeData.name)) return;
        
        // =====================================================================
        // FLOW LOGIN
        // =====================================================================
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
                
                // Login Button
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
                            flowState.loggedIn = true;
                            flowState.userName = result.user_name;
                            node.bgcolor = FLOW_COLOR_SUCCESS;
                            btnWidget.name = "✓ " + result.user_name;
                            if (node.statusWidget) {
                                node.statusWidget.value = "Connected to " + result.site_url;
                            }
                        } else {
                            node.loginStatus = { loggedIn: false, userName: "" };
                            flowState.loggedIn = false;
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
                        const btn = this.widgets?.find(w => w.type === "button");
                        if (btn) btn.name = "✓ Connected";
                    }
                }
                this.setDirtyCanvas(true);
            };
        }
        
        // =====================================================================
        // PROJECT BROWSER - Dynamic dropdown
        // =====================================================================
        else if (nodeData.name === "ProjectBrowser") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated?.apply(this, []);
                
                const node = this;
                
                // Refresh button
                const refreshBtn = this.addWidget("button", "refresh", "↻ Load Projects", async () => {
                    if (node.projectDropdown) {
                        await node.projectDropdown.refresh();
                    }
                });
                
                // Project dropdown
                node.projectDropdown = createDynamicDropdown(
                    node, 
                    "project_select",
                    async () => {
                        const resp = await api.fetchApi("/vfx-flow/projects");
                        const data = await resp.json();
                        return data.success ? data.projects : [];
                    },
                    (project) => {
                        flowState.selectedProject = project;
                        if (node.infoWidget) {
                            node.infoWidget.value = `✓ Selected: ${project.name}\nID: ${project.id}`;
                        }
                        // Notify other nodes
                        app.graph._nodes.forEach(n => {
                            if (n.type === "ShotBrowser" && n.sequenceDropdown) {
                                n.sequenceDropdown.refresh();
                            }
                        });
                    }
                );
                
                // Info display
                this.infoWidget = ComfyWidgets["STRING"](this, "info_display", ["STRING", { multiline: true }], app).widget;
                this.infoWidget.inputEl.readOnly = true;
                this.infoWidget.inputEl.style.opacity = 0.8;
                this.infoWidget.inputEl.style.fontSize = "11px";
                this.infoWidget.inputEl.style.minHeight = "50px";
                this.infoWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        
        // =====================================================================
        // SHOT BROWSER - Sequence + Shot dropdowns
        // =====================================================================
        else if (nodeData.name === "ShotBrowser") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated?.apply(this, []);
                
                const node = this;
                
                // Sequence dropdown
                node.sequenceDropdown = createDynamicDropdown(
                    node,
                    "sequence_select", 
                    async () => {
                        if (!flowState.selectedProject) return [];
                        const resp = await api.fetchApi(`/vfx-flow/sequences?project_id=${flowState.selectedProject.id}`);
                        const data = await resp.json();
                        return data.success ? data.sequences : [];
                    },
                    (seq) => {
                        flowState.selectedSequence = seq;
                        if (node.shotDropdown) {
                            node.shotDropdown.refresh();
                        }
                    }
                );
                
                // Shot dropdown  
                node.shotDropdown = createDynamicDropdown(
                    node,
                    "shot_select",
                    async () => {
                        if (!flowState.selectedProject) return [];
                        let url = `/vfx-flow/shots?project_id=${flowState.selectedProject.id}`;
                        if (flowState.selectedSequence) {
                            url += `&sequence_id=${flowState.selectedSequence.id}`;
                        }
                        const resp = await api.fetchApi(url);
                        const data = await resp.json();
                        return data.success ? data.shots : [];
                    },
                    async (shot) => {
                        flowState.selectedShot = shot;
                        
                        // Set to In Progress
                        try {
                            await api.fetchApi("/vfx-flow/select", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ type: "shot", id: shot.id, set_in_progress: true })
                            });
                        } catch (e) {}
                        
                        if (node.infoWidget) {
                            node.infoWidget.value = `✓ Shot: ${shot.code}\nSequence: ${shot.sequence}\nStatus: In Progress`;
                        }
                        
                        // Notify task selectors
                        app.graph._nodes.forEach(n => {
                            if (n.type === "TaskSelector" && n.taskDropdown) {
                                n.taskDropdown.refresh();
                            }
                        });
                    }
                );
                
                // Refresh button
                this.addWidget("button", "refresh", "↻ Refresh", async () => {
                    await node.sequenceDropdown?.refresh();
                    await node.shotDropdown?.refresh();
                });
                
                // Info display
                this.infoWidget = ComfyWidgets["STRING"](this, "info_display", ["STRING", { multiline: true }], app).widget;
                this.infoWidget.inputEl.readOnly = true;
                this.infoWidget.inputEl.style.opacity = 0.8;
                this.infoWidget.inputEl.style.fontSize = "11px";
                this.infoWidget.inputEl.style.minHeight = "60px";
                this.infoWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        
        // =====================================================================
        // TASK SELECTOR - Dynamic task dropdown
        // =====================================================================
        else if (nodeData.name === "TaskSelector") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function() {
                onNodeCreated?.apply(this, []);
                
                const node = this;
                
                // Task dropdown
                node.taskDropdown = createDynamicDropdown(
                    node,
                    "task_select",
                    async () => {
                        if (!flowState.selectedShot) return [];
                        const resp = await api.fetchApi(`/vfx-flow/tasks?shot_id=${flowState.selectedShot.id}`);
                        const data = await resp.json();
                        return data.success ? data.tasks : [];
                    },
                    async (task) => {
                        flowState.selectedTask = task;
                        
                        // Select task in backend
                        try {
                            await api.fetchApi("/vfx-flow/select", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ type: "task", id: task.id })
                            });
                        } catch (e) {}
                        
                        if (node.infoWidget) {
                            node.infoWidget.value = `✓ Task: ${task.name}\nStep: ${task.step}\nStatus: ${task.status}`;
                        }
                    }
                );
                
                // Refresh button
                this.addWidget("button", "refresh", "↻ Refresh Tasks", async () => {
                    await node.taskDropdown?.refresh();
                });
                
                // Info display
                this.infoWidget = ComfyWidgets["STRING"](this, "info_display", ["STRING", { multiline: true }], app).widget;
                this.infoWidget.inputEl.readOnly = true;
                this.infoWidget.inputEl.style.opacity = 0.8;
                this.infoWidget.inputEl.style.fontSize = "11px";
                this.infoWidget.inputEl.style.minHeight = "50px";
                this.infoWidget.serializeValue = async () => "";
                
                this.color = FLOW_COLOR;
                this.bgcolor = FLOW_COLOR_DARK;
            };
        }
        
        // =====================================================================
        // OTHER NODES (PublishToFlow, AddNote, FilenameFromFlow)
        // =====================================================================
        else if (["PublishToFlow", "AddNote"].includes(nodeData.name)) {
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
        
        // Watermark for all nodes
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
        console.log("[VFX Flow] Dynamic dropdowns loaded");
    }
});
