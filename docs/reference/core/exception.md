# Exception API

## Exception Hierarchy

```tree
Exception
└─ BaseError
   ├─ ApiError
   │  ├─ ApiDataError
   │  ├─ CredentialError
   │  │  ├─ LoginExpiredError
   │  │  └─ NotLoginError
   │  ├─ SignInvalidError
   │  └─ RatelimitedError
   ├─ HTTPError
   ├─ LoginError
   └─ NetworkError
```

::: qqmusic_api.core.exceptions
