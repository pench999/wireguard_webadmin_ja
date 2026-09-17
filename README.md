## 🌍 他の言語で読む
- 🇯🇵 [日本語](README.md)
- 🇬🇧 [English](https://github.com/eduardogsilva/wireguard_webadmin/blob/main/README.md)
- 🇧🇷 [Português](docs/README.pt-br.md)
- 🇪🇸 [Español](docs/README.es.md)
- 🇫🇷 [Français](docs/README.fr.md)
- 🇩🇪 [Deutsch](docs/README.de.md)

翻訳に問題がある場合や、新しい言語の追加を希望する場合は、[issue](https://github.com/pench999/wireguard_webadmin_ja/issues) からお知らせください。


# wireguard_webadmin 日本語版

**セルフホスト型の VPN 管理と Zero Trust アクセス制御を、すべて自分のインフラ上で運用できます。**

wireguard_webadmin は、単なる WireGuard 管理パネルではありません。ピア、ファイアウォールルール、DNS、ポート転送を管理でき、さらに認証付きで内部アプリケーションを公開できます。外部の第三者サービスに依存せず、Docker が動作する Linux マシンで利用できます。無料・オープンソースで、データは自分のサーバー内に留まります。

このリポジトリは [eduardogsilva/wireguard_webadmin](https://github.com/eduardogsilva/wireguard_webadmin) の UI 日本語化フォークです。

- ⚙️ **管理** - 複数の WireGuard インスタンス、ピア通信グラフ、ファイアウォール、DNS ブラックリスト、QR コード付き VPN 招待リンク
- 🔒 **保護** - TOTP、IP ACL、ブルートフォース対策 (Altcha PoW) を備えた Zero Trust アプリケーションゲートウェイ
- ⚡ **自動化** - ピアアクセスのスケジュール制御、ルーティングテンプレート、有効期限付き招待リンク、REST API v2

### 📖 詳細なドキュメント、インストール手順、設定のヒントは [wireguard-webadmin.com](https://wireguard-webadmin.com/) を参照してください

---

## クイックインストール

日本語版を利用する場合は、このフォークを clone して起動してください。

```bash
git clone https://github.com/pench999/wireguard_webadmin_ja.git wireguard_webadmin
cd wireguard_webadmin

cp .env.example .env
nano .env

docker compose -f docker-compose-caddy.yml up -d --build
```

`.env` の `SERVER_ADDRESS` は、利用者がアクセスするサーバーのIPアドレスまたはDNS名に変更してください。Caddyを使わず既存のリバースプロキシ配下で動かす場合は、`docker-compose-no-caddy.yml` を使います。

`docker-compose-no-caddy.yml` で直接Djangoへアクセスする場合は、例として次のようにポートを公開します。

```yaml
ports:
  - "18000:8000"
```

この場合の管理画面URLは次の形式です。

```text
http://<サーバーIP>:18000/
```

`.env` の `EXTRA_ALLOWED_HOSTS` には、実際にブラウザからアクセスするホスト名またはIPアドレスを指定してください。

```env
SERVER_ADDRESS=192.168.22.76
EXTRA_ALLOWED_HOSTS=192.168.22.76,192.168.22.76:18000,localhost,127.0.0.1
TIMEZONE=Asia/Tokyo
```

日本語版では、このリポジトリ内のソースコードから Docker イメージをビルドします。`--build` を付けずに起動すると、古いローカルイメージが再利用されて翻訳や修正が反映されない場合があります。

すでに起動済みの環境を日本語版へ更新する場合は、リポジトリを更新してからコンテナを再作成してください。

```bash
cd wireguard_webadmin
git pull
docker compose -f docker-compose-caddy.yml up -d --build --force-recreate
docker exec wireguard-webadmin python manage.py migrate
```

`docker-compose-no-caddy.yml` を使っている場合は、上記の `docker-compose-caddy.yml` を `docker-compose-no-caddy.yml` に読み替えてください。

詳細な手順、アップグレードガイド、設定のヒントは **[wireguard-webadmin.com](https://wireguard-webadmin.com/)** を参照してください。

日本語版の運用補足として、[ピア管理マニュアル](docs/peer_management_ja.md)、[ピア管理マニュアル Word版](docs/peer_management_ja.docx)、[クライアントセットアップ手順書](docs/client_setup_ja.md)、[クライアントセットアップ手順書 Word版](docs/client_setup_ja.docx) も用意しています。

---

## VPNユーザーポータルと接続前MFA

この日本語版では、エンドユーザー向けに `/vpn/` ポータルを利用できます。

管理者はユーザー権限に `VPNユーザー` を選択し、ピア設定画面で対象ピアに `割当ユーザー` を設定します。ユーザーは共通URL `/vpn/` へログインすると、自分に割り当てられたピアだけを確認できます。

ユーザーへ案内するURLは共通です。

```text
http://<サーバーIPまたはホスト名>:<ポート>/vpn/
```

例:

```text
http://192.168.22.76:18000/vpn/
```

運用手順:

1. 管理者がユーザーを作成し、権限を `VPNユーザー` に設定します。
2. 管理者がピアを作成します。
3. ピア設定画面で `割当ユーザー` を設定します。
4. 必要に応じて、そのピアを `MFA必須` にします。
5. ユーザーへ `/vpn/` の共通URL、ユーザー名、初期パスワードを通知します。
6. MFA未設定の場合、ユーザー本人が認証アプリでMFAを設定します。
7. MFA必須ピアは、ユーザー本人のMFA認証後に管理者が設定した時間だけVPN接続が有効になります。
8. ユーザーは `/vpn/` から本人用の設定ファイルまたはQRコードを取得します。

`VPNユーザー` は通常の管理画面へアクセスできません。`/status/`、`/peer/list/`、`/user/list/` などへ直接アクセスしても `/vpn/` へ戻されます。

接続前MFAは、WireGuard自体のプロトコルにMFAを追加するものではありません。MFA認証に成功したピアだけを一定時間 WireGuard 設定へ反映し、期限切れ後に cron が再度ロックする方式です。

### 管理者側の設定

管理者は通常の管理画面で次を設定します。

- `ユーザー管理` でユーザーを作成し、ユーザーレベルを `VPNユーザー` にします。
- `ピア設定` で対象ピアを開き、`割当ユーザー` にそのユーザーを設定します。
- 接続前MFAを使うピアでは `MFA必須にする` を有効化します。
- `MFAロック方式` を選択します。`時間でロック` は指定時間後にロックし、`切断検知でロック` は切断検知後にロックします。
- `MFA接続許可時間` で、認証成功後に接続を許可する時間を分単位で設定します。
- `切断検知でロック` を使う場合は、`MFA切断猶予秒数` で一時的な回線断を許容する秒数を設定します。
- `登録済みブラウザのみMFA認証を許可` を有効にすると、ユーザーがMFAを設定したブラウザからのみVPN接続のMFA認証を許可します。
- 必要に応じて、ピアのVPNアドレス、クライアント側Allowed IP、DNS、ルーティングテンプレートを設定します。

管理者とスーパーユーザーは、すべてのピアに対してMFAコードなしで `VPN接続を有効化` できます。これは利用者本人のMFA認証が使えない場合の管理操作を想定した例外で、監査ログには管理者バイパスとして記録されます。

`VPNユーザー` は管理画面の閲覧権限を持ちません。管理者向けの閲覧だけを許可したい場合は `閲覧のみ`、ピア管理も許可したい場合は `ピア管理者` を使ってください。

### ユーザー側の使い方

ユーザーは `/vpn/` にログインして、自分に割り当てられたピアだけを操作します。

- `MFA設定`: 認証アプリでTOTPを設定します。
- `パスワード変更`: VPNポータルへログインするパスワードをユーザー本人が変更します。
- `VPN接続を有効化`: MFA必須ピアを管理者が設定した時間だけ有効化します。
- `設定ファイル`: WireGuardクライアントへインポートする `.conf` を取得します。
- `QRコード`: スマートフォン版WireGuardアプリで読み取るQRコードを表示します。

パスワードは12文字以上で、英大文字・英小文字・数字・記号をそれぞれ1文字以上含める必要があります。この条件は、VPNユーザー本人のパスワード変更だけでなく、管理者がユーザーを作成または更新する場合にも適用されます。

MFA認証に使うTOTPはユーザー本人が設定してください。管理者がユーザーのQRコードやシークレットを読み取る運用は、本人以外も同じMFAコードを生成できるため推奨しません。

MFAは初回設定後、ユーザー本人だけでは再設定できません。端末変更や認証アプリ紛失などで再設定が必要な場合は、管理者がユーザー管理画面から `再設定許可` を実行します。ユーザーが再設定を完了すると、再設定許可は自動的に解除されます。

`登録済みブラウザのみMFA認証を許可` は、MFA登録時にブラウザへ保存したCookieを照合する機能です。別端末、別ブラウザ、Cookie削除後はVPN接続のMFA認証ができなくなるため、管理者によるMFA再設定許可が必要です。この機能は端末本体を完全に識別するものではなく、登録済みブラウザを信頼する仕組みです。

### 監査ログ

接続前MFAに関連する操作は監査ログへ記録されます。

- MFA認証失敗
- MFAによるピア一時有効化
- 管理者権限によるピア一時有効化
- MFA期限切れによるピアロック
- ピアのMFA必須化
- ピアのMFA必須解除

監査ログは管理画面の `監査ログ` メニューから確認できます。表示には管理者権限、またはユーザー管理で `監査ログ` の閲覧権限が必要です。

### 注意事項

- MFA有効化はWireGuard設定ファイルの反映とインターフェースリロードを伴います。
- 期限切れ後のロックは cron により実行されます。cronコンテナが停止していると自動ロックが実行されません。
- 許可時間が切れると、対象ピアはWireGuard設定から外されます。接続中であっても通信は継続延長されず、リロード後に切断されます。
- `切断検知でロック` はWireGuardの明示的な切断イベントではなく、最終ハンドシェイク時刻からの推定です。`PersistentKeepalive` が有効な端末では接続中扱いが長く続く場合があります。
- `切断検知でロック` では、切断が検知されるまでピアは有効なままです。厳格な時間制限が必要なピアでは `時間でロック` を使ってください。
- ピアに `割当ユーザー` が設定されていない場合、そのピアは `/vpn/` ポータルには表示されません。
- 登録済みブラウザ制限はCookieを利用します。Cookieを盗まれた場合は突破される可能性があるため、管理画面やVPNポータルは必ずHTTPSで運用してください。
- `/vpn/` から取得できる設定ファイルには、ピアに秘密鍵が登録されている場合、その秘密鍵が含まれます。配布先と端末管理には注意してください。

---

## スクリーンショット

### ピア一覧
すべての WireGuard インスタンスに登録されたピアのリアルタイム状態とライブ帯域グラフを確認できます。
![ピア一覧](docs/images/peer_list_dark.png)

### ピア詳細
通信履歴、最終ハンドシェイク、許可 IP、QR コードを 1 画面で確認できます。
![ピア詳細](docs/images/peer_details.png)

### Zero Trust アプリケーションゲートウェイ
Proxmox や Grafana などの内部アプリケーションを、TOTP 認証付きで公開できます。直接ポートを開放する必要はありません。
![Zero Trust アプリケーションゲートウェイ](docs/images/zero_trust_app.png)

### ファイアウォール管理
インスタンスごとの iptables ルール、ポート転送、アウトバウンド ACL を UI から管理できます。
![ファイアウォール](docs/images/firewall.png)

### VPN 招待
QR コードと設定ファイルを含む共有用の招待を生成できます。ユーザーは WireGuard クライアントでスキャンまたはインポートするだけで利用できます。
![VPN 招待](docs/images/vpn_invite.png)

---

## ライセンス

このプロジェクトは MIT License で公開されています。詳細は [LICENSE](LICENSE) を参照してください。

## コントリビューション

不具合報告、翻訳改善、プルリクエストは歓迎します。日本語化に関する issue や pull request は、このフォークの [GitHub リポジトリ](https://github.com/pench999/wireguard_webadmin_ja) へお願いします。
