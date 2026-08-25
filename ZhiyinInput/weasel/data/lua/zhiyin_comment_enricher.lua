--[[ ====================================================================
-- zhiyin_comment_enricher.lua
-- 知音输入法 · 候选词拼音注释注入器
-- ====================================================================
--
-- 用途：
--   候选词 list 的每一项 candidate：
--     - 默认 comment 字段是空（除非人为设置）
--     - 我们把 candidate.spelling 注入到 candidate.comment
--     - 候选词上方显示完整拼音（带声调）
--
--   举例：候选词 "吃" 拼音 "chi2"
--     不加注释前：
--       1. 吃
--     加注释后：
--       1. 吃     [chi2]
--
-- 关联：
--   与 zhiyin_spelling_switch.lua 协同；
--   拼音声调从 env.engine.context:get_property("zhiyin_spelling_round") 读取
--
-- 作者：李子旺
-- 许可证：Apache-2.0
-- ==================================================================== ]]

local M = {}

function M.init(env) return true end
function M.fini(env) return true end

-- 数字 → 声调字符
local tones = { "⁰", "¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹" }

local function format_spelling(spelling)
  if not spelling or spelling == "" then
    return ""
  end
  -- spelling 是拼音不带声调数字时也能用；
  -- 我们只在末尾追加声调
  -- 这里简化：直接返回原 spelling + 数字声调提示
  return spelling
end

function M.filter(cand_list, env)
  local ctx = env.engine.context
  local round = tonumber(ctx:get_property("zhiyin_spelling_round")) or 0

  for i, cand in ipairs(cand_list) do
    if cand.spelling and cand.spelling ~= "" then
      -- 只在 round == 0 时显示完整拼音
      -- 其余轮数由 zhiyin_spelling_expander 处理（更高优先级）
      if round == 0 then
        cand.comment = cand.spelling or ""
      end
    end
  end

  return cand_list
end

return M
