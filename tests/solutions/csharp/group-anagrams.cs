using System.Text;

public class Solution {
    public IList<IList<string>> GroupAnagrams(string[] strs) {
        var groups = new Dictionary<string, IList<string>>();
        foreach (string s in strs) {
            var counts = new int[26];
            foreach (char c in s) counts[c - 'a']++;
            var key = new StringBuilder();
            foreach (int n in counts) key.Append('#').Append(n);
            string k = key.ToString();
            if (!groups.TryGetValue(k, out var group)) {
                group = new List<string>();
                groups[k] = group;
            }
            group.Add(s);
        }
        return groups.Values.ToList();
    }
}
