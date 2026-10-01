# Bunch of AIgents (BoA)

이 README는 다음 언어로도 볼 수 있습니다:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [hi-IN](README.hi-IN.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## 무엇인가요

GNU/Linux 서버(Debian 또는 Alpine)에서 각자 별도의 사용자로 실행되는 셀프 호스팅 AI 에이전트입니다.

각 에이전트는 다음을 각자 가집니다:

- 홈 디렉터리
- crontab
- 셸 접근
- Samba 공유
- RAG(필요한 경우)
- 기타

웹 앱에서 바로, 또는 Telegram이나 Discord를 통해 이용할 수 있습니다.

## 스크린샷

![Bunch of AIgents 인터페이스](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## 설치

`root`로 실행하세요.

**Debian**(systemd가 PID 1인 경우):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine에는 Playwright가 없습니다.** Playwright는 musl용 빌드를 내놓지
> 않으므로 Alpine의 에이전트에게는 브라우저가 없습니다. 에이전트가 `browser.*`
> 도구를 호출하면 그 도구가 그렇다고 알려 줍니다. 그 밖의 모든 것은 Debian과
> 똑같이 동작합니다.

## 문서 읽기

더 알아보기:

- [doc/MANUAL.ko-KR.md](doc/MANUAL.ko-KR.md): 설치, 설정, 사용 방법을 배울 수 있습니다.
- [doc/CODE.ko-KR.md](doc/CODE.ko-KR.md): 어떻게 만들어졌는지 알 수 있습니다(개발자와 AI 모델용).

## 이 프로젝트 후원하기

- **개발 의뢰.** 개인이든 기업이든 새 기능 추가를 의뢰할 수 있습니다: [메일 보내기](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo).
- **커피 한 잔 사 주기:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun).
- **GitHub Sponsors.** GitHub에서 프로젝트를 금전적으로 후원할 수도 있습니다: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun).
