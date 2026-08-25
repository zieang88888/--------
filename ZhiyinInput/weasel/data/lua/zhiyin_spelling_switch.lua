--[[ ====================================================================
-- zhiyin_spelling_switch.lua
-- 知音输入法 · 拼音循环切换 / 多音字切换 处理器
-- ====================================================================
--
-- 用途：
--   监听 `\` 或 `Shift+Tab`（已由 key_binder/bindings 映射成 Shift+Tab），
--   当输入状态（composing + has_menu）时：
--     1. 在 current_spelling_index 这一个上下文属性上累计
--     2. 把候选词的多个拼音注入到 candidate.comment
--     3. 候选窗上方变成可点击切换的拼音按钮（由 weasel 渲染显示）
--
-- 工作原理：
--   Rime 的候选词有 .spelling 内置属性（拼音）。
--   当 Lua 处理器在 context 里写一个属性 current_spelling_index，
--   在 zhiyin_comment_enricher.lua filter 中读取并修改 cand.comment
--   这样候选词上方可以显示 "chi1 / chi2" 这样的多个拼音声调。
--
-- 附：因为 librime 实际只能对每个 candidate 保留一个 spelling，
-- 真正的"循环切换"靠的是 selector 的 multi-syllable 能力。
-- 在我们这里通过 candidate.quality 的提升让高频拼音靠前来模拟切换。
--
-- 作者：李子旺
-- 许可证：Apache-2.0
-- ==================================================================== ]]

-- 候选词拼音多音字切换的本地状态
local spelling_state = {
  cursor = 0,        -- 当前候选词序号
  round = 0,         -- 当前切换轮数
  last_size = 0,     -- 上次候选词条数
}

-- 模块入口
local M = {}

function M.init(env)
  env.zhiyin_spelling_state = spelling_state
  return true
end

function M.fini(env)
  return true
end

-- 切换到下一个拼音
-- 通过 context:set_property 通知 UI 渲染
local function switch_spelling(env, ctx, direction)
  local cand_list_size = 0
  if ctx.candidates then
    cand_list_size = #ctx.candidates
  end

  -- 计算轮次 (0 → 1 → 2 → ...)
  local round = (env.zhiyin_spelling_state.round + 1) % 4
  env.zhiyin_spelling_state.round = round

  -- 通知 UI：
  -- 知音工具栏进程通过 \\.\pipe\ZhiyinToolbar 收到 STATE_SPELLING_ROUND 广播
  ctx:set_property("zhiyin_spelling_round", tostring(round))
  ctx:set_property("zhiyin_spelling_timestamp", os.time())

  return true  -- accepted
end

-- 主处理器入口
function M.process(key, env)
  local ctx = env.engine.context
  if not ctx:is_composing() then
    return 2  -- kNoop
  end

  -- 候选词窗口存在？
  if not ctx:has_menu() then
    return 2
  end

  -- Shift+Tab: 已由 key_binder/bindings 转换成 Shift+Tab
  -- 但这里我们直接监听 release 事件
  if key:release() then
    return 2  -- 释放事件不处理
  end

  -- 触发：Shift+Tab 或 `\`
  local is_shift_tab = (key:repr() == "Shift+Tab" or
                       (key:modifiers() == 1 and key:keycode() == 0xff09))
  local is_backslash = (key:repr() == "\\" or key:keycode() == 0xdc)
  -- 兼容 Shift+\（用户在小键盘上）
  is_backslash = is_backslash or (key:repr() == "Shift+\\")

  if is_shift_tab or is_backslash then
    local direction = is_backslash and "next" or "next"
    return switch_spelling(env, ctx, direction) and 1 or 2  -- 1 = kAccepted
  end

  return 2  -- kNoop
end

return M
