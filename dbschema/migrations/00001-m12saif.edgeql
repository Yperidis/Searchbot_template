CREATE MIGRATION m12saif7ks4zjygbpccou26xlcne54amkdxt74gyok2eifka74xitq
    ONTO initial
{
  CREATE FUTURE simple_scoping;
  CREATE TYPE default::Message {
      CREATE PROPERTY body: std::str;
      CREATE PROPERTY role: std::str;
      CREATE MULTI PROPERTY sources: std::str;
      CREATE PROPERTY timestamp: std::datetime {
          SET default := (std::datetime_current());
      };
  };
  CREATE TYPE default::Chat {
      CREATE MULTI LINK messages: default::Message;
  };
  CREATE TYPE default::User {
      CREATE MULTI LINK chats: default::Chat;
      CREATE PROPERTY name: std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
};
