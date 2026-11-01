func groupAnagrams(strs []string) [][]string {
    groups := map[string][]string{}
    for _, s := range strs {
        chars := strings.Split(s, "")
        sort.Strings(chars)
        key := strings.Join(chars, "")
        groups[key] = append(groups[key], s)
    }
    res := [][]string{}
    for _, g := range groups {
        res = append(res, g)
    }
    return res
}
