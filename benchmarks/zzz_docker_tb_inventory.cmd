@echo off
cd /d E:\project\agent\xiaopu
(
  echo identity=%USERNAME%
  echo === docker info ===
  docker info --format "{{.ServerVersion}}|{{.MemTotal}}"
  echo === containers ===
  docker ps -a --format "{{.ID}}|{{.Names}}|{{.Status}}" --filter "name=hello-world-1-of-1-xiaopu" --filter "name=extract-safely-1-of-1-xiaopu" --filter "name=fix-permissions-1-of-1-xiaopu"
  echo === disk ===
  docker system df
) > workspace\results\zzz_docker_tb_inventory.log 2>&1
