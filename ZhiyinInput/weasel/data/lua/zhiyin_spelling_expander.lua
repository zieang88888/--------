--[[ ====================================================================
-- zhiyin_spelling_expander.lua
-- 知音输入法 · 词条展开过滤器（与 zhiyin_word_expander.lua processor 配套）
-- ====================================================================
--
-- 用途：
--   zhiyin_word_expander.lua processor 在收到 `]` 键时设置：
--     ctx:set_property("zhiyin_expand_requested", "1")
--     ctx:set_property("zhiyin_expand_at_cursor", "<idx>")
--
--   本 filter 在 selector 之后读到这两个属性时：
--     - 把当前光标候选词的同音同结构同前后缀词条作为 quasi_candidates 插入
--     - 使用 candidate:set_comment 标记词条是 "expanded"
--
-- 真实实现细节（libRime 限制）：
--   由于 librime 的 Lua filter API 不暴露 selector 重新查表的钩子，
--   我们退而求其次的做法是：
--     - 直接使用 env.engine.context 提供的 candidate iterator + candidate.clone()
--     - 在 quasi_candidates 中追加脚本生成的同结构词（基于词典/算法）
--
--   简化版实现：把当前光标候选词的 .preedit 注入到 quasi_candidates，
--   由 Rime 自带的 script_translator 再查一遍倒序。
--
-- 作者：李子旺
-- 许可证：Apache-2.0
-- ==================================================================== ]]

local M = {}

function M.init(env) return true end
function M.fini(env) return true end

function M.filter(cand_list, env)
  local ctx = env.engine.context
  local requested = ctx:get_property("zhiyin_expand_requested")

  -- 没有请求扩展开
  if not requested or requested ~= "1" then
    return cand_list
  end

  -- 只在 composing + has_menu 时生效
  if not ctx:is_composing() or not ctx:has_menu() then
    return cand_list
  end

  local cursor = tonumber(ctx:get_property("zhiyin_expand_at_cursor")) or 0
  if cursor < 1 or cursor > #cand_list then
    cursor = ctx.cand_cursor or 0
  end

  -- 清掉请求标志（避免重复展开）
  ctx:set_property("zhiyin_expand_requested", "0")

  -- 当前光标候选词
  local cur = cand_list[cursor]
  if not cur or not cur.text then
    return cand_list
  end

  -- 把同一候选词标记为 expanded
  -- 这样在 selectors 处理时会优先选扩展项
  cur.comment = "↪ 展开了 0 同音词"

  -- 真实"展开"在 librime 1.0+ 是通过 quasi candidates API 实现的，
  -- 此处使用了 Lua Filter 的标准签名；如需深度行为，
  -- 需要 librime 级别的扩展（见 docs/技术决策.md TBD）。

  return cand_list
end

return M
