"""Fixed trusted Git HTTPS profile: sealed repository config and host credential, readonly source/candidate, no model executable or arbitrary arguments.

Only fixed Git HTTPS commands use the shared host network. This is program/argv
confinement, not a kernel destination ACL. Native model profiles remain unchanged.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from backend.runtime import _domain_spawn
from backend.runtime.broker_profile import _syscall_filter
from backend.runtime.contracts import RunConflict
from backend.runtime.development_workspace import _POLICY
from backend.runtime.publication_capsule import (
    PEER_PUBLICATION_CANDIDATE,
    PublicationGitCapsule,
    PublicationGitLaunch,
)
from backend.runtime.remote_publication import RemotePushIntent
from backend.runtime.workspaces import PEER_WORKSPACE

_EXTRA = ("-c", "uploadpack.packObjectsHook=", "-c", "transfer.fsckObjects=true")


@dataclass(frozen=True, kw_only=True)
class RemoteGitLaunch(PublicationGitLaunch):
    """Immutable exact accepted remote command and operator configuration identity; it contains no PAT or author-selected executable."""

    intent: RemotePushIntent
    transport_identity: str

    def __post_init__(self):
        """Allow only required readonly Git observations or the original exact HTTPS query/push; no mixed stdin/local write capability."""
        super().__post_init__()
        if (
            not isinstance(self.intent, RemotePushIntent)
            or (self.intent.head_sha, self.intent.base_sha)
            != (self.view.head_sha, self.view.base_sha)
            or self.input_text is not None
        ):
            raise ValueError("Remote launch differs from its exact accepted candidate")
        if len(self.transport_identity) != 64:
            raise ValueError("Original operator transport identity required")
        if self.arguments not in self.allowed_commands:
            raise ValueError(
                "Git command is outside the fixed remote publication profile"
            )
        candidate = str(PEER_PUBLICATION_CANDIDATE)
        if self.arguments in self.local_candidate_commands:
            if self.cwd != candidate:
                raise ValueError(
                    "Candidate validation must use its readonly captured view"
                )
        elif self.cwd != str(PEER_WORKSPACE):
            raise ValueError("Remote commands must use the original readonly source")

    @property
    def local_candidate_commands(self):
        """List only the exact candidate validation observations used by the shared reviewed-code policy."""
        return {
            (*_POLICY, "rev-parse", "--verify", "HEAD^{commit}"),
            (*_POLICY, "rev-parse", "--verify", "HEAD^{tree}"),
            (
                *_POLICY,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--binary",
                "--full-index",
                "--no-color",
                "--no-renames",
                self.intent.base_sha,
                self.intent.head_sha,
                "--",
            ),
            (*_POLICY, "ls-files", "-z", "--", ".ken"),
            (
                *_POLICY,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".",
                ":(top,exclude).ken",
            ),
        }

    @property
    def allowed_commands(self):
        """Bind remote refspecs and all global Git options to the original immutable protocol."""
        return self.local_candidate_commands | {
            (
                *_POLICY,
                *_EXTRA,
                "merge-base",
                "--is-ancestor",
                self.intent.base_sha,
                self.intent.head_sha,
            ),
            (*_POLICY, *_EXTRA, *self.intent.query_arguments),
            (*_POLICY, *_EXTRA, *self.intent.push_arguments),
        }

    @property
    def is_write(self):
        """Identify the one exact original atomic push, rather than searching user text for a command name."""
        return self.arguments == (*_POLICY, *_EXTRA, *self.intent.push_arguments)

    @property
    def networked(self):
        """Grant networking only for the exact remote query or push; candidate inspections retain the no-network profile."""
        return self.is_write or self.arguments == (
            *_POLICY,
            *_EXTRA,
            *self.intent.query_arguments,
        )


class RemoteGitCapsule(PublicationGitCapsule):
    """Own pinned Git and private mounts while preventing repository config/URL rewrites from changing the credential destination."""

    def __init__(self, binding, launch, info_fd, *, remote_transport):
        """Take credential access only from the actual broker operator configuration, never the launch or source repository."""
        if (
            not isinstance(launch, RemoteGitLaunch)
            or remote_transport.identity != launch.transport_identity
            or remote_transport.api_base != launch.intent.remote.api_base
        ):
            raise RunConflict(
                "Remote transport differs from original configured origin"
            )
        for path in (
            remote_transport.token_file,
            Path(remote_transport.network.ca_bundle.path),
            Path(remote_transport.network.resolver.path),
        ):
            if path.is_relative_to(binding.workspace) or path.is_relative_to(
                launch.view.workspace
            ):
                raise RunConflict(
                    "Remote host credentials/trust must stay outside source views"
                )
        super().__init__(binding, launch, info_fd)
        self.remote_transport = remote_transport
        self._remote_fds = []

    def _network(self):
        """Expose host network only to the fixed trusted HTTPS Git program; this is not a model/network capability."""
        return ["--share-net"] if self.launch.networked else []

    def _filter(self):
        """Keep namespace/ptrace/listener protections while allowing the fixed HTTPS client's outbound sockets only when needed."""
        return _syscall_filter(network=self.launch.networked, protected_peers=True)

    def _program(self):
        """Pin Git first, then inject the URL-scoped header inside its private namespace rather than in argv or durable manifests."""
        super()._program()
        env = dict(self.launch.environment)
        env.update(GIT_GRAFT_FILE="/dev/null", GIT_NO_REPLACE_OBJECTS="1")
        code = "import os,json,base64;env=" + repr(env) + ";"
        if self.launch.networked:
            code += (
                "cred=json.load(open('/run/researcher-remote/credential'));env.update(GIT_SSL_CAINFO='/run/researcher-network/ca.pem',GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0="
                + repr("http." + self.launch.intent.remote.clone_url + ".extraHeader")
                + ",GIT_CONFIG_VALUE_0='Authorization: Basic '+base64.b64encode((cred['username']+':'+cred['token']).encode()).decode());"
            )
        code += (
            "os.chdir("
            + repr(self.launch.cwd)
            + ");os.execve("
            + repr(self.launch.asset.path)
            + ","
            + repr([self.launch.asset.path, *self.launch.arguments])
            + ",env)"
        )
        return [str(Path(sys.executable).resolve(strict=True)), "-I", "-S", "-c", code]

    def _mounts(self):
        """Pin original metadata readonly and overlay only sealed safe configuration; no source file or Git config is modified."""
        view = self.launch.view
        source = self._directory(view.source_metadata)
        from backend.runtime.publication_git import PublicationDirectory

        candidate = self._directory(
            PublicationDirectory(view.workspace, view.device, view.inode)
        )
        metadata = self._directory(view.candidate_metadata)
        version = "1" if len(view.head_sha) == 64 else "0"
        config = "[core]\nrepositoryformatversion=" + version + "\nbare=false\n"
        if version == "1":
            config += "[extensions]\nobjectFormat=sha256\n"
        fixed = _domain_spawn.sealed(config.encode())
        self._stack.callback(os.close, fixed)
        self._remote_fds.append(fixed)
        candidate_fixed = _domain_spawn.sealed(config.encode())
        self._stack.callback(os.close, candidate_fixed)
        self._remote_fds.append(candidate_fixed)
        mounts = [
            "--ro-bind-fd",
            str(self._asset_fd),
            self.launch.asset.path,
            "--ro-bind-fd",
            str(source),
            str(PEER_WORKSPACE / ".git"),
            "--ro-bind-fd",
            str(candidate),
            str(PEER_PUBLICATION_CANDIDATE),
            "--ro-bind-fd",
            str(metadata),
            str(PEER_PUBLICATION_CANDIDATE / ".git"),
            "--ro-bind-data",
            str(fixed),
            str(PEER_WORKSPACE / ".git/config"),
            "--ro-bind-data",
            str(candidate_fixed),
            str(PEER_PUBLICATION_CANDIDATE / ".git/config"),
        ]
        if self.launch.networked:
            fds = self._stack.enter_context(self.remote_transport.network.opened())
            self._remote_fds.extend(fds.values())
            secret = _domain_spawn.sealed(
                json.dumps(
                    {
                        "username": self.remote_transport.username,
                        "token": self.remote_transport.token(),
                    }
                ).encode()
            )
            self._stack.callback(os.close, secret)
            self._remote_fds.append(secret)
            mounts += [
                "--dir",
                "/run/researcher-network",
                "--dir",
                "/run/researcher-remote",
                "--ro-bind-data",
                str(fds["resolver"]),
                "/etc/resolv.conf",
                "--ro-bind-data",
                str(fds["ca_bundle"]),
                "/run/researcher-network/ca.pem",
                "--ro-bind-data",
                str(secret),
                "/run/researcher-remote/credential",
            ]
        return mounts

    def __enter__(self):
        """Retain sealed credential/config/trust descriptors only through the original gated spawn."""
        super().__enter__()
        self.pass_fds += tuple(self._remote_fds)
        return self
