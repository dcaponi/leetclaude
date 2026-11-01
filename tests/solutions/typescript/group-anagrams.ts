function groupAnagrams(strs: string[]): string[][] {
    const groups = new Map<string, string[]>();
    for (const s of strs) {
        const counts = new Array<number>(26).fill(0);
        for (const ch of s) counts[ch.charCodeAt(0) - 97]++;
        const key = counts.join("#");
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(s);
    }
    return [...groups.values()];
};
