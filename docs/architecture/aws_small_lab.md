# AWS 소형 실모델 배포 실습

2026-10-09 서울 리전에서 비용을 제한한 비공개 실습을 진행했다. 운영 배포나 외부 사용자 공개가 아니다. 로컬 Kubernetes 실습은 [`deploy/kind/README.md`](../../deploy/kind/README.md)에 따로 기록했다.

## 계정과 비용 경계

이 계정은 Free Plan에서 `t4g.xlarge` 생성이 거절되었다 (`InvalidParameterCombination: The specified instance type is not eligible for Free Tier`). AWS가 Free Tier 대상으로 표시한 `m7i-flex.large`(x86_64, 8GiB)를 선택했다. 기존에 중지된 다른 EC2 인스턴스와 20GiB gp3 볼륨, 연결된 Elastic IP가 있으므로 새 서버만 따로 계산한 값을 계정 전체 비용으로 표현하지 않는다.

AWS Price List API에서 2026-10-09 조회한 서울 리전 공개 온디맨드 단가는 다음과 같다.

| 항목 | 단가 | 적용 범위 |
|---|---:|---|
| `m7i-flex.large` Linux 인스턴스 | $0.11771/시간 | 실행 중에만 |
| gp3 볼륨 | $0.0912/GB-월 | 볼륨을 보존하는 동안 |
| 공인 IPv4 | $0.005/시간 | 할당된 동안 |

새 서버는 20GiB gp3 볼륨을 사용한다. 중지한 뒤 새 서버의 인스턴스와 공인 IPv4 요금은 멈추지만, 볼륨은 월 전체를 보존하면 공개 단가 기준 $1.824가 든다. 기존 20GiB 볼륨과 Elastic IP를 730시간 보유한다는 가정의 공개 단가 합계는 월 $5.474다. 따라서 이 두 기존 항목과 새 중지된 서버의 볼륨은 월 $7.298이다. 이는 **환율·세금·Free Plan 크레딧·기타 AWS 사용량을 제외한 가정값**이다. Cost Explorer는 `User not enabled for cost explorer access`로 조회되지 않아 실제 청구액을 확인하지 못했다. AWS Budgets 알림만으로 정확한 5만 원 자동 차단을 보장하지 않는다.

## 실행 계약

- Amazon Linux 2023 x86_64, `m7i-flex.large`, 루트 20GiB gp3를 사용한다.
- `Dockerfile`의 `ml-cpu-runtime`은 PyTorch 2.8.0 CPU 전용 wheel을 공식 CPU 저장소에서 설치한다. 일반 `ml-runtime`과 분리해 GPU 이미지 계약을 바꾸지 않는다.
- 모델은 `kakaocorp/kanana-1.5-2.1b-instruct-2505`의 고정 리비전 `7df4bc35ccd610e451809d7106e1c3cf82bfd44c`을 서버 로컬 디스크에 둔다.
- PostgreSQL과 API는 Docker의 내부 네트워크로만 연결하고 API는 서버의 `127.0.0.1:8001`에만 바인드한다. 보안 그룹은 실습 당시 컴퓨터의 IP에서 SSH(22)만 허용한다.
- 첫 부팅 스크립트에 2시간 후 OS 종료를 예약하고, `instance-initiated-shutdown-behavior=stop`으로 설정했다. 재부팅에도 적용되도록 `maeumcall-lab-stop.timer`를 `enabled`·`active` 상태로 설치했으며 `OnBootSec=2h`의 다음 실행 시간을 확인했다. 검증 직후에는 CLI에서 직접 중지했다.
- OpenAI·Firebase·Kakao 값은 로컬 실습용 더미다. `/health/ready`의 이 항목들은 실제 외부 인증 성공을 검증하지 않는다. TTS는 비활성화한다.

## 2026-10-09 검증 결과

1. x86_64 CPU 이미지를 빌드하고 이미지 내부에서 `torch 2.8.0+cpu`, `torch.cuda.is_available() == False`, `transformers 4.57.3`을 확인했다.
2. AWS 서버에서 고정 모델 다운로드, PostgreSQL 시작, Alembic 마이그레이션, API 시작이 성공했다.
3. 서버의 루프백에서 `/health/ready`가 HTTP 200이었다.
4. 병원 예약 요청 한 턴이 HTTP 200으로 약 64.0초에 끝났고, `department=내과`, `date=내일`, `conversationState=asking_time`이었다. 단일 요청이며 성능·품질 벤치마크가 아니다.
5. 새 인스턴스는 `stopped` 상태이고 공인 IPv4가 남지 않은 것을 확인했다. 20GiB gp3 볼륨과 전용 보안 그룹·키 페어는 재실습용으로 보존했다.

## 다시 실습할 때

AWS 콘솔이나 CLI에서 `Project=maeumcall-ai-server`, `Purpose=temporary-lab` 태그가 붙은 **새 실습 인스턴스**만 찾는다. 시작 전에 다른 EC2·볼륨·IP와 구분하고 비용 예산을 다시 확인한다. 중지된 서버를 시작하면 공인 IP가 바뀔 수 있으므로 `describe-instances`로 새 주소를 읽는다. SSH 개인키는 저장소가 아닌 사용자 `.ssh/maeumcall-lab-20261009`에 권한 600으로 보관했다. 보안 그룹의 SSH 허용 IP가 현재 컴퓨터와 다르면 먼저 갱신해야 한다.

Docker 서비스는 부팅 시 시작한다. 컨테이너는 자동 재시작하지 않으므로 서버에서 `sudo docker start maeumcall-postgres`를 실행하고 `pg_isready`를 확인한 뒤 `sudo docker start maeumcall-api`를 실행한다. 먼저 `systemctl list-timers maeumcall-lab-stop.timer`에서 자동 중지 예약을 확인한다. 외부 포트를 열지 말고 SSH 터널로 `127.0.0.1:8001`에 접속한다. 실습 뒤 인스턴스를 중지하고 `stopped`와 `PublicIpAddress=None`을 확인한다. 더 이상 재실습할 필요가 없을 때만 인스턴스를 종료하여 20GiB 루트 볼륨도 삭제한다.

## 참고

- [AWS EC2 온디맨드 과금](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-on-demand-instances.html)
- [AWS EBS 요금](https://aws.amazon.com/ebs/pricing/)
- [AWS 공인 IPv4 요금](https://aws.amazon.com/vpc/pricing/)
- [AWS Free Tier EC2 대상](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)
- [PyTorch 2.8.0 CPU 설치](https://pytorch.org/get-started/previous-versions/)
