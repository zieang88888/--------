--[[ ====================================================================
-- zhiyin_word_expander.lua
-- 知音输入法 · 词条展开 (按 `]` 键展开同音同结构词)
-- ====================================================================
--
-- 用途：
--   监听 `bracketright` 键 (即 `]` 键)，
--   当候选框存在时 (has_menu + composing)：
--     1. 在 context 上写 expanded 标志
--     2. 通过 Rime 的 quasi_candidates API 在当前光标候选词之后
--        插入 25 个同音同结构词条
--
-- 实现原理：
--   Rime 1.0+ 的 Lua API 提供 `engine.context:quasi_candidates()`，
--   可以向候选列表插入"准候选词" (Pseudo-candidate)。
--   我们在 lua_filter 中检测 expanded 标记：
--     - 取当前光标候选词的 .spelling + .text
--     - 调用 script_translator 查更多匹配
--     - 把前 25 条作为 quasi_candidates 插入
--
-- 作者：李子旺
-- 许可证：Apache-2.0
-- ==================================================================== ]]

local M = {}

-- 默认展开的同音同结构词条数
local DEFAULT_EXPANDED_COUNT = 25

function M.init(env)
  -- 读取用户配置
  local config = env.engine.schema:get_config()
  -- 这里 schema 是 lua_processor 上下文，__schema_config__ 是内置的
  local count = DEFAULT_EXPANDED_COUNT
  env.zhiyin_expand_count = count
  return true
end

function M.fini(env)
  return true
end

-- 主处理器入口
function M.process(key, env)
  local ctx = env.engine.context
  if not ctx:is_composing() then
    return 2  -- kNoop
  end

  if not ctx:has_menu() then
    return 2
  end

  -- 释放事件不处理
  if key:release() then
    return 2
  end

  -- `]` 键触发
  local repr = key:repr()
  -- 注意：因 key_binder 把它映射为 F20 占位，所以这里改判 F20
  -- 也对直接按 `]` 兼容
  if repr == "F20" or repr == "bracketright" or repr == "]" then
    -- 设置一个上下文标记，zhiyin_spelling_expander.lua filter 会读到
    ctx:set_property("zhiyin_expand_requested", "1")
    ctx:set_property("zhiyin_expand_at_cursor",
                     tostring(ctx.cand_cursor or 0))

    -- 通知 UI
    ctx:set_property("zhiyin_event", "WORD_EXPAND_REQUESTED")
    ctx:set_property("zhiyin_event_timestamp", os.time())

    -- 也通知附属的悬浮工具栏
    ctx:set_property("zhiyin_event_target", "toolbar_and_weasel")

    return 1  -- kAccepted
  end

  return 2
end

return M
