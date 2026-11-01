# @param {String} s
# @param {String[]} word_dict
# @return {Boolean}
def word_break(s, word_dict)
  words = word_dict.to_set
  dp = Array.new(s.size + 1, false)
  dp[0] = true
  (1..s.size).each do |i|
    dp[i] = (0...i).any? { |j| dp[j] && words.include?(s[j...i]) }
  end
  dp[s.size]
end
