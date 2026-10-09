# 로컬 Kubernetes 실습

이 디렉터리는 `kind` 클러스터에서 PostgreSQL → Alembic Job → 실모델 API 순서로 실행하는 로컬 실습용이다. `hostPath`, 로컬 이미지와 더미 외부 자격 증명에 의존하므로 AWS나 운영 클러스터에 그대로 적용하지 않는다.

## 준비

- Docker Engine, `kubectl`, `kind`가 필요하다.
- `maeum-call-ai-server:2.2.0-core`와 `maeum-call-ai-server:2.2.0-ml` 이미지를 현재 코드에서 빌드한다.
- `scripts.prepare_hf_model_cache`로 고정된 모델 리비전을 호스트 캐시에 내려받는다. 캐시는 약 4.3GB이고 절대 경로로 지정한다.
- 기존 Kubernetes 컨텍스트를 오용하지 않도록 전용 kubeconfig를 모든 명령에 명시한다.

```bash
export HF_MODEL_CACHE_DIR=/absolute/path/to/huggingface/cache
export LAB_KUBECONFIG=/private/tmp/maeumcall-kind-kubeconfig

docker build --target core-runtime --tag maeum-call-ai-server:2.2.0-core .
docker build --target ml-runtime --tag maeum-call-ai-server:2.2.0-ml .
mkdir -p "$HF_MODEL_CACHE_DIR"
docker run --rm --user 0:0 \
  --volume "$HF_MODEL_CACHE_DIR:/models" --env HF_HOME=/models \
  --entrypoint python maeum-call-ai-server:2.2.0-ml \
  -m scripts.prepare_hf_model_cache

cat > /private/tmp/maeumcall-kind-config.yaml <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: $HF_MODEL_CACHE_DIR
        containerPath: /models
        readOnly: true
EOF

kind create cluster --name maeumcall-lab \
  --config /private/tmp/maeumcall-kind-config.yaml \
  --kubeconfig "$LAB_KUBECONFIG"
kind load docker-image maeum-call-ai-server:2.2.0-core \
  maeum-call-ai-server:2.2.0-ml --name maeumcall-lab
```

다음 Secret은 **로컬 기능 확인 전용 더미값**이다. 실제 OpenAI·Firebase·Kakao 호출에 사용하지 않는다. 값이 존재한다는 readiness 항목은 외부 서비스 인증 성공을 뜻하지 않는다. 실자격 증명은 저장소에 넣지 않는다.

```bash
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  create namespace maeumcall-lab

kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  -n maeumcall-lab create secret generic maeumcall-lab \
  --from-literal=POSTGRES_PASSWORD=lab-only-password \
  --from-literal='DATABASE_URL=postgresql+asyncpg://maeumcall:lab-only-password@postgres:5432/maeumcall' \
  --from-literal=OPENAI_API_KEY=lab-no-external-openai-requests \
  --from-literal=BASELINE_ID_HMAC_SECRET=lab-only-baseline-secret-32-characters \
  --from-literal=AUTH_SUBJECT_HMAC_SECRET=lab-only-subject-secret-32-characters \
  --from-literal=KAKAO_APP_ID=lab-only-kakao-app \
  --from-literal=FIREBASE_PROJECT_ID=lab-only-firebase-project

kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  apply -f deploy/kind/postgres.yaml
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  -n maeumcall-lab rollout status deployment/postgres --timeout=180s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  apply -f deploy/kind/migrate.yaml
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  -n maeumcall-lab wait --for=condition=complete job/maeumcall-migrate --timeout=180s
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  apply -f deploy/kind/api.yaml
kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab \
  -n maeumcall-lab rollout status deployment/maeumcall-api --timeout=300s
```

확인할 때는 `kubectl ... port-forward -n maeumcall-lab service/maeumcall-api 18001:8001`을 별도 터미널에서 실행하고, `http://127.0.0.1:18001/health/ready`를 조회한다. 모델·DB 준비 상태는 HTTP 200이어야 한다. `POST /chat`의 응답 내용과 상태 전이도 별도로 확인한다. `ready`의 OpenAI·인증 항목은 여기서는 더미 구성 검사만 통과한다.

2026-10-09 Apple Silicon Docker 환경에서 kind v0.33.0 / Kubernetes v1.37.0으로 확인했다. PostgreSQL Pod와 API Pod가 `1/1 Running`, 마이그레이션 Job은 `Complete`였다. `/health/ready`는 200, 병원 예약 요청 한 턴은 200으로 `asking_time` 상태가 되었고 약 36.9초 걸렸다. 이 한 번의 CPU 실행은 성능 벤치마크가 아니다.

확인 후 노트북 메모리를 돌려주기 위해 API Deployment를 `replicas=0`으로 낮췄다. 다시 실습할 때는 `kubectl --kubeconfig "$LAB_KUBECONFIG" --context kind-maeumcall-lab -n maeumcall-lab scale deployment/maeumcall-api --replicas=1`로 시작하고 rollout을 기다린다.

실습을 끝내고 **이 클러스터의 테스트 DB까지 삭제해도 될 때만** 다음 명령으로 전용 클러스터를 지운다.

```bash
kind delete cluster --name maeumcall-lab --kubeconfig "$LAB_KUBECONFIG"
```
