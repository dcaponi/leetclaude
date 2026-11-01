# @param {Character[][]} grid
# @return {Integer}
def num_islands(grid)
  m, n = grid.size, grid[0].size
  count = 0
  m.times do |i|
    n.times do |j|
      next unless grid[i][j] == "1"
      count += 1
      stack = [[i, j]]
      grid[i][j] = "0"
      until stack.empty?
        x, y = stack.pop
        [[1, 0], [-1, 0], [0, 1], [0, -1]].each do |dx, dy|
          nx, ny = x + dx, y + dy
          next if nx < 0 || ny < 0 || nx >= m || ny >= n || grid[nx][ny] != "1"
          grid[nx][ny] = "0"
          stack << [nx, ny]
        end
      end
    end
  end
  count
end
