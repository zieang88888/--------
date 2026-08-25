--[[ ====================================================================
-- zhiyin_toolbar_hotkey.lua
-- 知音输入法 · 悬浮工具栏全局热键 / 启动外部进程
-- ====================================================================
--
-- 用途：
--   监听：
--     F21 (Ctrl+Alt+L)    → 显隐悬浮工具栏
--     F22 (Ctrl+Alt+V)    → 启动 Windows 11 系统语音输入 (ms-inputapp://)
--     F23 (Ctrl+Alt+H)    → 启动 Windows 10/11 系统手写输入 (tabtip.exe)
--
--   这些键已经在 schema 的 key_binder/bindings 中被映射到 F21/F22/F23。
--   F21/F22/F23 是不会出现在键盘上的特殊键，所以可以无副作用地"吃掉"。
--
--   当 Lua 捕获后，通过 context:set_property("zhiyin_event", "X") 通知
--   WeaselServer 与悬浮工具栏进程联动。
--
-- 作者：李子旺
-- 许可证：Apache-2.0
-- ==================================================================== ]]

local M = {}

-- Windows API 调用（Lua 中不直接支持，实际在 WeaselServer 端实现）
-- 这里只能通过 context:set_property 与 WeaselServer 通信

function M.init(env) return true end
function M.fini(env) return true end

local function launch_process_via_weasel(env, ctx, command)
  -- 写入一个属性，WeaselServer 端的 zhiyin_ipc_bridge 线程会读到并执行
  ctx:set_property("zhiyin_external_command", command)
  ctx:set_property("zhiyin_external_command_ts", os.time())
  ctx:set_property("zhiyin_event", "EXTERNAL_COMMAND")
  ctx:set_property("zhiyin_event_target", "weasel_server")
end

function M.process(key, env)
  local ctx = env.engine.context
  if key:release() then
    return 2
  end

  local repr = key:repr()

  if repr == "F21" then
    -- 显隐悬浮工具栏
    ctx:set_property("zhiyin_event", "TOGGLE_TOOLBAR")
    ctx:set_property("zhiyin_event_ts", os.time())
    return 1
  elseif repr == "F22" then
    -- 启动 Windows 11 语音输入 (ms-inputapp://)
    -- Win10 会因找不到协议而失败；悬浮工具栏进程应当捕获失败并提示
    launch_process_via_weasel(env, ctx, "ms-inputapp://")
    return 1
  elseif repr == "F23" then
    -- 启动系统手写输入
    launch_process_via_weasel(env, ctx, "tabtip.exe")
    return 1
  end

  return 2
end

return M
