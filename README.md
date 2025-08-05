# dlog - Docker Swarm 远程日志查看工具

dlog 是一个命令行工具，用于查看远程 Docker Swarm 服务的日志，并支持关键字搜索和高亮显示。

## 功能特性

- 通过 SSH 连接到远程主机查看 Docker Swarm 服务日志
- 支持模糊匹配服务名称
- 关键字搜索和高亮显示
- 实时日志跟踪（follow模式）
- 大小写不敏感搜索
- 可配置默认 SSH 目标

## 安装

确保系统已安装 Python 3 和 SSH 客户端。

将 `dlog.py` 脚本复制到系统 PATH 路径中，例如 `/usr/local/bin/dlog`，并确保其具有可执行权限：

```bash
chmod +x dlog.py
sudo cp dlog.py /usr/local/bin/dlog
```

## 配置

### 配置文件

dlog 支持通过配置文件设置默认 SSH 目标。配置文件应位于脚本同目录下的 `dlog.conf` 文件中。

示例配置文件 `dlog.conf`：
```ini
[default]
target = user@hostname
```

### SSH 配置

确保您已配置好 SSH 密钥认证，以便无需密码即可连接到远程主机。

## 使用方法

### 基本语法

```bash
dlog [SSH目标] <服务名称> [关键字] [选项]
```

### 参数说明

- `SSH目标`: SSH 连接信息，格式为 `user@host`。如果在配置文件中设置了默认目标，可以省略此参数。
- `服务名称`: Docker Swarm 服务名称（支持模糊匹配）。
- `关键字`: 要搜索的关键字（可选）。

### 选项

- `-n LINES`, `--lines LINES`: 显示最近的 LINES 行日志（默认：100）
- `-f`, `--follow`: 实时跟踪日志输出
- `-i`, `--ignore-case`: 忽略大小写进行搜索

### 使用示例

#### 1. 查看服务最近100行日志

```bash
dlog user@host my-service
```

#### 2. 搜索包含特定关键字的日志

```bash
dlog user@host my-service ERROR
```

#### 3. 实时跟踪日志并高亮显示关键字

```bash
dlog user@host my-service ERROR -f
```

#### 4. 显示更多历史日志

```bash
dlog user@host my-service ERROR -n 500
```

#### 5. 忽略大小写搜索

```bash
dlog user@host my-service error -i
```

#### 6. 使用配置文件中的默认目标

如果在 `dlog.conf` 中配置了默认目标：
```ini
[default]
target = dev-server
```

则可以直接使用：
```bash
dlog my-service ERROR
```

#### 7. 模糊匹配服务名称

如果服务名称为 `my-app-api`，可以使用部分名称匹配：
```bash
dlog user@host api ERROR
```

## 注意事项

- 确保远程主机上已安装 Docker 并正在运行 Docker Swarm
- 确保 SSH 用户具有执行 `docker service logs` 命令的权限
- 当使用 `-f` 选项时，按 `Ctrl+C` 可以退出实时日志跟踪模式
