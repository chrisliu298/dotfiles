## Capacity, devboxes, data

```bash
$M resource groups get --json '{"sid":"1043","options":{"include_resources":true}}'
#   free = .group.resources.clusters[] | select(.cluster_sid=="47") | .queues[] | select(.node_type=="gpu")
#          → total.gpu["NVIDIA-H20"] − used.gpu["NVIDIA-H20"]   (my-group-resources list lacks this)
$M gpu-devbox instances get --json '{"instance_sid":"<sid>"}'     # list: '{}'
$M cpu-devbox instances get --json '{"sid":"<sid>"}'
$M data datacards get --json '{"name":"<datacard>","options":{"include_detail":true}}'
$M knowledge-v2 bases query --json '{"query":"…","limit":5}'      # platform docs Q&A with citations
```

