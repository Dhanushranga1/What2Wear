# StyleSync Phase 4 Operations Runbook

## Quick Reference

### Emergency Contacts
- On-call Engineer: `@oncall-stylesync`
- Platform Team: `@platform-team`
- API Team: `@api-team`

### Key URLs
- Production API: `https://api.stylesync.com`
- Staging API: `https://staging-api.stylesync.com`
- Monitoring: `https://grafana.stylesync.com/d/phase4`
- Logs: `https://kibana.stylesync.com`
- Metrics: `https://prometheus.stylesync.com`

## Service Overview

StyleSync Phase 4 is a unified orchestrator providing color advice through a single `/v1/advice` endpoint. The service coordinates Phase 1 (segmentation), Phase 2 (extraction), and Phase 3 (harmony) with advanced caching, security, and observability.

### Architecture Components
- **Orchestrator**: Main service coordinating phase pipeline
- **Multi-Layer Cache**: Redis + in-memory LRU fallback
- **Security Layer**: API key auth + rate limiting
- **Observability**: Structured logs + Prometheus metrics + OpenTelemetry traces
- **Reliability**: Circuit breakers + timeouts + graceful degradation

## Common Operations

### Service Status Check

```bash
# Health check
curl -f https://api.stylesync.com/v1/healthz

# Readiness check (includes dependencies)
curl -f https://api.stylesync.com/v1/readyz

# Metrics endpoint
curl https://api.stylesync.com/v1/metrics | grep stylesync_
```

### Log Analysis

```bash
# Recent errors
kubectl logs -l app=stylesync-api --since=1h | grep ERROR

# Request tracing
kubectl logs -l app=stylesync-api | grep "request_id=req_abc123"

# Performance analysis
kubectl logs -l app=stylesync-api | grep "total_processing_time_ms" | tail -100
```

### Cache Management

```bash
# Connect to Redis
kubectl exec -it redis-pod -- redis-cli

# Cache statistics
> INFO keyspace
> INFO stats

# Check specific cache keys
> SCAN 0 MATCH "stylesync:l1:*" COUNT 10
> GET "stylesync:l1:content_hash:abc123"

# Clear cache (emergency only)
> FLUSHDB  # ⚠️ Use with caution
```

### Performance Monitoring

```bash
# Request rate and latency
curl -s https://prometheus.stylesync.com/api/v1/query?query=rate\(stylesync_requests_total\[5m\]\)

# P95 latency
curl -s "https://prometheus.stylesync.com/api/v1/query?query=histogram_quantile(0.95,rate(stylesync_request_duration_seconds_bucket[5m]))"

# Cache hit rates
curl -s https://prometheus.stylesync.com/api/v1/query?query=stylesync_cache_hit_ratio
```

## Incident Response

### Alert Classification

#### **P0 - Critical (5min response)**
- Service completely down (`up{job="stylesync-api"} == 0`)
- Error rate >50% for >2 minutes
- P95 latency >10 seconds

#### **P1 - High (15min response)**
- Error rate >10% for >5 minutes
- P95 latency >2 seconds for >5 minutes
- Cache hit rate <30% for >10 minutes

#### **P2 - Medium (1hr response)**
- Elevated error rate 5-10%
- P95 latency 1-2 seconds
- Individual phase timeouts

#### **P3 - Low (Next business day)**
- Minor performance degradation
- Capacity warnings
- Non-critical feature issues

### Incident Response Steps

#### 1. Initial Assessment (2 minutes)
```bash
# Check service status
kubectl get pods -l app=stylesync-api
kubectl get svc stylesync-api-service

# Check recent deployments
kubectl rollout history deployment/stylesync-api

# Quick error scan
kubectl logs -l app=stylesync-api --since=10m | grep -E "(ERROR|FATAL|CRITICAL)" | tail -20
```

#### 2. Immediate Mitigation (5 minutes)
```bash
# Scale up if performance issue
kubectl scale deployment stylesync-api --replicas=6

# Restart if deployment issue
kubectl rollout restart deployment/stylesync-api

# Check external dependencies
curl -f $REDIS_URL/ping
aws s3 ls $S3_BUCKET --region $AWS_REGION
```

#### 3. Detailed Investigation (15 minutes)
```bash
# Identify error patterns
kubectl logs -l app=stylesync-api --since=1h | grep ERROR | sort | uniq -c | sort -nr

# Check resource usage
kubectl top pods -l app=stylesync-api

# Database/cache status
kubectl exec -it redis-pod -- redis-cli INFO memory
kubectl exec -it redis-pod -- redis-cli INFO clients
```

#### 4. Resolution and Recovery
```bash
# Gradual rollback if needed
kubectl rollout undo deployment/stylesync-api

# Clear problematic cache if corrupted
kubectl exec -it redis-pod -- redis-cli FLUSHDB

# Validate resolution
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
    -H "X-API-Key: $TEST_API_KEY" \
    -d "base_color=#FF0000&target_role=bottom" \
    https://api.stylesync.com/v1/advice
  sleep 1
done
```

## Troubleshooting Guides

### High Latency Issues

**Symptoms**: P95 latency >2 seconds

**Investigation**:
```bash
# Check phase-specific timings
kubectl logs -l app=stylesync-api | grep "phase.*_duration_ms" | tail -50

# Identify slow phases
curl -s "https://prometheus.stylesync.com/api/v1/query?query=histogram_quantile(0.95,rate(stylesync_phase_duration_seconds_bucket[5m]))"

# Check cache performance
kubectl exec -it redis-pod -- redis-cli --latency-history -i 1
```

**Common Causes & Solutions**:
1. **Phase 1 Segmentation Slow**
   - Check GPU utilization: `nvidia-smi`
   - Verify model loading: `kubectl logs -l app=stylesync-api | grep "model.*loaded"`
   - Scale up GPU nodes: `kubectl scale nodepool gpu-pool --replicas=3`

2. **Cache Misses**
   - Monitor hit rates: `stylesync_cache_hit_ratio`
   - Check Redis memory: `kubectl exec -it redis-pod -- redis-cli INFO memory`
   - Increase cache TTL if appropriate

3. **Network Latency**
   - Check inter-service latency
   - Verify load balancer health
   - Consider regional deployment

### High Error Rate

**Symptoms**: Error rate >10%

**Investigation**:
```bash
# Error breakdown by type
kubectl logs -l app=stylesync-api --since=1h | grep ERROR | \
  jq -r '.error_type' | sort | uniq -c | sort -nr

# Recent failed requests
kubectl logs -l app=stylesync-api | grep '"status": [45]' | tail -20
```

**Common Causes & Solutions**:
1. **Authentication Failures (401)**
   - Check API key configuration
   - Verify rate limiting settings
   - Review client implementations

2. **Validation Errors (400)**
   - Check input parameter validation
   - Review recent API changes
   - Monitor client error patterns

3. **Timeout Errors (503)**
   - Increase timeout settings if justified
   - Check circuit breaker status
   - Scale up processing capacity

4. **Dependency Failures (502/503)**
   - Check Redis connectivity
   - Verify S3 access
   - Test phase component health

### Cache Issues

**Symptoms**: Low cache hit rates or cache errors

**Investigation**:
```bash
# Cache statistics
kubectl exec -it redis-pod -- redis-cli INFO stats
kubectl exec -it redis-pod -- redis-cli INFO keyspace

# Memory usage
kubectl exec -it redis-pod -- redis-cli INFO memory

# Connection status
kubectl exec -it redis-pod -- redis-cli INFO clients
```

**Solutions**:
1. **Low Hit Rates**
   ```bash
   # Analyze cache key patterns
   kubectl exec -it redis-pod -- redis-cli --scan --pattern "*" | head -20
   
   # Check TTL settings
   kubectl exec -it redis-pod -- redis-cli TTL "stylesync:l1:content_hash:example"
   ```

2. **Memory Issues**
   ```bash
   # Clear expired keys
   kubectl exec -it redis-pod -- redis-cli --scan --pattern "*" | \
     xargs -I {} kubectl exec -it redis-pod -- redis-cli TTL {}
   
   # Scale Redis if needed
   kubectl patch statefulset redis --type='merge' -p='{"spec":{"template":{"spec":{"containers":[{"name":"redis","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
   ```

3. **Connection Issues**
   ```bash
   # Check network connectivity
   kubectl exec -it stylesync-api-pod -- nc -zv redis-service 6379
   
   # Review connection pooling
   kubectl logs -l app=stylesync-api | grep "redis.*connection"
   ```

### Circuit Breaker Activation

**Symptoms**: Degraded responses with fallback suggestions

**Investigation**:
```bash
# Check circuit breaker status
kubectl logs -l app=stylesync-api | grep "circuit.*breaker" | tail -20

# Monitor degraded responses
kubectl logs -l app=stylesync-api | grep '"degraded": true' | tail -10
```

**Actions**:
1. **Identify Failing Phase**
   ```bash
   # Check which phase is triggering breakers
   kubectl logs -l app=stylesync-api | grep "circuit.*OPEN" | grep -o "phase[0-9]"
   ```

2. **Manual Circuit Reset** (if appropriate)
   ```bash
   # Restart pods to reset circuit breakers
   kubectl rollout restart deployment/stylesync-api
   ```

3. **Investigate Root Cause**
   - Check phase-specific logs
   - Verify model availability
   - Test phase endpoints individually

## Maintenance Procedures

### Planned Deployment

```bash
# 1. Pre-deployment checks
kubectl get pods -l app=stylesync-api -o wide
kubectl top pods -l app=stylesync-api

# 2. Create deployment backup
kubectl get deployment stylesync-api -o yaml > backup-deployment.yaml

# 3. Rolling update
kubectl set image deployment/stylesync-api api=stylesync/api:v1.0.1

# 4. Monitor rollout
kubectl rollout status deployment/stylesync-api --timeout=300s

# 5. Validate deployment
./scripts/validate-deployment.sh

# 6. Rollback if needed
kubectl rollout undo deployment/stylesync-api
```

### Cache Warming

```bash
# Warm cache with common requests
./scripts/warm-cache.sh

# Monitor cache build-up
watch -n 5 'kubectl exec -it redis-pod -- redis-cli INFO keyspace'
```

### Database Maintenance

```bash
# Redis maintenance
kubectl exec -it redis-pod -- redis-cli BGREWRITEAOF
kubectl exec -it redis-pod -- redis-cli BGSAVE

# Check persistence
kubectl exec -it redis-pod -- redis-cli LASTSAVE
```

### Capacity Planning

```bash
# Current resource usage
kubectl top pods -l app=stylesync-api
kubectl top nodes

# Request rate trends
curl -s "https://prometheus.stylesync.com/api/v1/query_range?query=rate(stylesync_requests_total[5m])&start=$(date -d '1 week ago' -u +%Y-%m-%dT%H:%M:%SZ)&end=$(date -u +%Y-%m-%dT%H:%M:%SZ)&step=1h"

# Scale recommendations
kubectl exec -it stylesync-api-pod -- python -c "
import psutil
cpu_percent = psutil.cpu_percent(interval=5)
memory_percent = psutil.virtual_memory().percent
print(f'CPU: {cpu_percent}%, Memory: {memory_percent}%')
if cpu_percent > 70 or memory_percent > 80:
    print('Consider scaling up')
"
```

## Configuration Management

### Environment Variables

```bash
# View current configuration
kubectl get configmap stylesync-config -o yaml

# Update configuration
kubectl patch configmap stylesync-config --type merge -p='{"data":{"STYLESYNC_CACHE_L1_TTL":"86400"}}'

# Apply changes (restart required)
kubectl rollout restart deployment/stylesync-api
```

### Security Updates

```bash
# Rotate API keys
kubectl create secret generic stylesync-api-key --from-literal=api-key=new-key-value

# Update TLS certificates
kubectl create secret tls stylesync-tls --cert=cert.pem --key=key.pem

# Apply security patches
kubectl set image deployment/stylesync-api api=stylesync/api:v1.0.1-security
```

## Monitoring Setup

### Key Dashboards

1. **Service Overview**
   - Request rate, latency, error rate
   - Cache hit ratios
   - Resource utilization

2. **Phase Performance**
   - Per-phase processing times
   - Phase success rates
   - Circuit breaker status

3. **Infrastructure**
   - Pod health and restarts
   - Node resource usage
   - Network metrics

### Alert Configuration

```yaml
# Prometheus alert rules
groups:
- name: stylesync-phase4
  rules:
  - alert: StyleSyncHighErrorRate
    expr: rate(stylesync_requests_total{status!="200"}[5m]) > 0.1
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "StyleSync error rate is {{ $value | humanizePercentage }}"
      
  - alert: StyleSyncHighLatency
    expr: histogram_quantile(0.95, rate(stylesync_request_duration_seconds_bucket[5m])) > 2.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "StyleSync P95 latency is {{ $value }}s"
```

## Performance Tuning

### Cache Optimization

```bash
# Adjust TTL based on hit patterns
kubectl patch configmap stylesync-config --type merge -p='{"data":{
  "STYLESYNC_CACHE_L1_TTL": "604800",
  "STYLESYNC_CACHE_L2_ADVICE_TTL": "7200"
}}'

# Increase cache memory
kubectl patch statefulset redis --type='merge' -p='{"spec":{"template":{"spec":{"containers":[{"name":"redis","args":["redis-server","--maxmemory","2gb","--maxmemory-policy","allkeys-lru"]}]}}}}'
```

### Resource Allocation

```bash
# CPU optimization
kubectl patch deployment stylesync-api --type='merge' -p='{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"requests":{"cpu":"500m"},"limits":{"cpu":"1000m"}}}]}}}}'

# Memory optimization
kubectl patch deployment stylesync-api --type='merge' -p='{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"requests":{"memory":"1Gi"},"limits":{"memory":"2Gi"}}}]}}}}'
```

### Autoscaling

```bash
# Configure HPA
kubectl autoscale deployment stylesync-api --min=3 --max=10 --cpu-percent=70

# Monitor scaling events
kubectl get hpa stylesync-api -w
```

## Disaster Recovery

### Backup Procedures

```bash
# Configuration backup
kubectl get configmaps,secrets -o yaml > config-backup.yaml

# Redis backup
kubectl exec -it redis-pod -- redis-cli BGSAVE
kubectl cp redis-pod:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb
```

### Recovery Procedures

```bash
# Restore from backup
kubectl apply -f config-backup.yaml

# Redis restore
kubectl cp ./redis-backup.rdb redis-pod:/data/dump.rdb
kubectl delete pod redis-pod  # Restart to load backup
```

### Cross-Region Failover

```bash
# Switch traffic to backup region
kubectl patch service stylesync-api-service -p '{"spec":{"selector":{"region":"us-west-2"}}}'

# Verify failover
curl -H "X-API-Key: $API_KEY" https://api.stylesync.com/v1/healthz
```

---

## Contact Information

- **Escalation Path**: P0 → On-call → Platform Team → Engineering Manager
- **Documentation**: https://docs.stylesync.com/phase4
- **Repository**: https://github.com/stylesync/phase4-api
- **Slack Channels**: #stylesync-alerts, #platform-team, #api-team

For questions or updates to this runbook, contact the Platform Team.
